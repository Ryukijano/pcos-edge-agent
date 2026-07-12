import Foundation
import LiteRTLM

/// LiteRT-LM Manager for iOS — handles Engine → Conversation pipeline with Metal GPU.
///
/// Uses the official LiteRT-LM Swift API (v0.14.0):
/// - Engine: model loading with CPU/GPU (Metal) backend selection
/// - Conversation: per-chat inference with system instruction and sampling config
/// - MTP/speculative decoding enabled for GPU backends
/// - RAM-based model auto-selection: picks E2B Mobile / E2B / E4B based on device RAM
@MainActor
class LiteRTManager: ObservableObject {

    static let shared = LiteRTManager()

    // MARK: - Device Tier

    enum DeviceTier: String {
        case lowEnd    // < 4GB RAM — E2B Mobile only
        case midRange  // 4-8GB RAM — E2B
        case highEnd   // 8+GB RAM — E4B
    }

    enum PCOSModel: String, CaseIterable {
        case functionGemma = "functiongemma-270m"
        case gemma4E2B = "gemma-4-E2B-it"
        case gemma4E4B = "gemma-4-E4B-it"
        case gemma4E2BMobile = "gemma-4-E2B-it-mobile"
        case gemma4E4BMobile = "gemma-4-E4B-it-mobile"

        var displayName: String {
            switch self {
            case .functionGemma: return "FunctionGemma 270M (CPU)"
            case .gemma4E2B: return "Gemma 4 E2B 2.3B (Metal)"
            case .gemma4E4B: return "Gemma 4 E4B 4.5B (Metal)"
            case .gemma4E2BMobile: return "Gemma 4 E2B Mobile 1GB (QAT)"
            case .gemma4E4BMobile: return "Gemma 4 E4B Mobile 2.2GB (QAT)"
            }
        }

        var fileName: String {
            switch self {
            case .functionGemma: return "functiongemma-270m-ft-mobile-actions.litertlm"
            case .gemma4E2B: return "gemma-4-E2B-it.litertlm"
            case .gemma4E4B: return "gemma-4-E4B-it.litertlm"
            case .gemma4E2BMobile: return "gemma-4-E2B-it-mobile.litertlm"
            case .gemma4E4BMobile: return "gemma-4-E4B-it-mobile.litertlm"
            }
        }
    }

    // MARK: - State

    @Published var engine: Engine?
    @Published var conversation: Conversation?
    @Published var currentModel: PCOSModel?
    @Published var activeBackend: String = "unknown"
    @Published var isLoaded = false
    @Published var isLoading = false
    @Published var selectedImageData: Data? = nil

    private let cacheDir = NSTemporaryDirectory()

    // MARK: - Model Capabilities

    /// Models that support vision (image) inputs.
    private let visionModels: Set<PCOSModel> = [.gemma4E4B, .gemma4E4BMobile]

    /// Models that support audio inputs.
    private let audioModels: Set<PCOSModel> = [.gemma4E4B, .gemma4E4BMobile]

    // MARK: - Device Detection

    /// Detect total device RAM in MB.
    var totalRamMb: Int {
        // Use Mach host_info for physical RAM
        var size = MemoryLayout<vm_size_data_t>.stride
        var info = vm_size_data_t()
        let hostPort = mach_host_self()
        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                host_statistics(hostPort, HOST_VM_INFO64, $0, &size)
            }
        }
        if result == KERN_SUCCESS {
            // Fallback: use process info
        }
        // Use sysctl for physical memory
        var mib: [Int32] = [CTL_HW, HW_MEMSIZE]
        var memSize: UInt64 = 0
        var len = MemoryLayout<UInt64>.size
        sysctl(&mib, 2, &memSize, &len, nil, 0)
        return Int(memSize / (1024 * 1024))
    }

    /// Classify device into tier based on RAM.
    var deviceTier: DeviceTier {
        let ram = totalRamMb
        if ram >= 8192 { return .highEnd }
        if ram >= 4096 { return .midRange }
        return .lowEnd
    }

    /// Detect Apple chip for Metal GPU support.
    var hasMetal: Bool {
        // All Apple A14+ and M1+ chips support Metal
        let processor = ProcessInfo.processinfo.processorCount
        return processor >= 6 // A14+ has 6 cores
    }

    /// Recommend best model for this device.
    func recommendModelForDevice(taskType: String = "chat") -> PCOSModel {
        switch deviceTier {
        case .lowEnd:
            return taskType == "action" ? .functionGemma : .gemma4E2BMobile
        case .midRange:
            if taskType == "action" { return .functionGemma }
            if taskType == "reasoning" { return .gemma4E4BMobile }
            return .gemma4E2B
        case .highEnd:
            if taskType == "action" { return .functionGemma }
            if taskType == "reasoning" || taskType == "multimodal" { return .gemma4E4B }
            return .gemma4E2B
        }
    }

    // MARK: - Engine Lifecycle

    /// Load a model into the LiteRT-LM engine with Metal GPU backend.
    func loadModel(_ model: PCOSModel) async throws {
        if currentModel == model && engine != nil { return }

        // Clean up previous
        try? conversation?.delete()
        try? engine?.delete()
        conversation = nil
        engine = nil

        isLoading = true
        defer { isLoading = false }

        // Find model file in bundle
        guard let modelUrl = Bundle.main.url(forResource: model.fileName, withExtension: nil) else {
            throw LiteRTError.modelNotFound(model.fileName)
        }

        // Enable MTP for Gemma 4 models on GPU
        if model != .functionGemma {
            ExperimentalFlags.optIntoExperimentalAPIs()
            ExperimentalFlags.enableSpeculativeDecoding = true
        }

        // Configure engine with Metal GPU backend
        let backend: Backend
        if hasMetal {
            backend = .gpu
            activeBackend = "Metal GPU"
        } else {
            backend = .cpu
            activeBackend = "CPU"
        }

        let engineConfig = try EngineConfig(
            modelPath: modelUrl.path,
            backend: backend,
            maxNumTokens: 8192,
            cacheDir: cacheDir
        )

        let eng = Engine(engineConfig: engineConfig)
        try await eng.initialize()

        // Create conversation with system instruction
        let convConfig = try ConversationConfig(
            systemInstruction: Contents.of(
                "You are a helpful on-device assistant running on iOS via LiteRT-LM."
            )
        )
        let conv = try await eng.createConversation(config: convConfig)

        engine = eng
        conversation = conv
        currentModel = model
        isLoaded = true
    }

    // MARK: - Inference

    /// Streaming inference — calls onChunk for each text token.
    func inferStreaming(_ prompt: String, onChunk: @escaping (String) -> Void) async throws -> String {
        guard let conv = conversation else {
            throw LiteRTError.engineNotLoaded
        }

        var result = ""
        let stream = try conv.sendMessageStreaming(prompt)
        for try await chunk in stream {
            for item in chunk.content {
                if item.type == .text {
                    result += item.text
                    onChunk(item.text)
                }
            }
        }
        return result
    }

    // MARK: - Multimodal Inference

    /// Check if the current model supports vision (image) inputs.
    func isVisionSupported() -> Bool {
        guard let model = currentModel else { return false }
        return visionModels.contains(model)
    }

    /// Check if the current model supports audio inputs.
    func isAudioSupported() -> Bool {
        guard let model = currentModel else { return false }
        return audioModels.contains(model)
    }

    /// One-shot multimodal inference with an image.
    ///
    /// Requires E4B model loaded (vision-capable). Returns error string if
    /// vision is not supported on the current model.
    func inferWithImage(prompt: String, imageData: Data) async -> String {
        guard let conv = conversation else {
            return "[Model not loaded]"
        }
        guard isVisionSupported() else {
            return "[Vision not supported on current model. Load E4B for multimodal.]"
        }

        do {
            let contents = Contents.of(text: prompt, images: [imageData])
            let response = try conv.sendMessage(contents)
            var result = ""
            for item in response.content {
                if item.type == .text {
                    result += item.text
                }
            }
            return result
        } catch {
            return "[Error: \(error.localizedDescription)]"
        }
    }

    /// Streaming multimodal inference with an image.
    ///
    /// Calls onChunk for each text token as it streams. Requires E4B model.
    func inferStreamingWithImage(
        prompt: String, imageData: Data, onChunk: @escaping (String) -> Void
    ) async -> String {
        guard let conv = conversation else {
            return "[Model not loaded]"
        }
        guard isVisionSupported() else {
            return "[Vision not supported on current model. Load E4B for multimodal.]"
        }

        do {
            let contents = Contents.of(text: prompt, images: [imageData])
            var result = ""
            let stream = try conv.sendMessageStreaming(contents)
            for try await chunk in stream {
                for item in chunk.content {
                    if item.type == .text {
                        result += item.text
                        onChunk(item.text)
                    }
                }
            }
            return result
        } catch {
            return "[Error: \(error.localizedDescription)]"
        }
    }

    /// Cancel ongoing generation.
    func cancel() {
        conversation?.cancel()
    }

    /// Clean up resources.
    func cleanup() async {
        try? conversation?.delete()
        try? engine?.delete()
        conversation = nil
        engine = nil
        currentModel = nil
        isLoaded = false
    }
}

// MARK: - Errors

enum LiteRTError: Error, LocalizedError {
    case modelNotFound(String)
    case engineNotLoaded

    var errorDescription: String? {
        switch self {
        case .modelNotFound(let name): return "Model file not found: \(name)"
        case .engineNotLoaded: return "LiteRT-LM engine not loaded"
        }
    }
}
