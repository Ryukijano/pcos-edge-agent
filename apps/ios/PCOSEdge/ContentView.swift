import SwiftUI
import LiteRTLM
import PhotosUI

/// Main chat view — SwiftUI interface for PCOS Edge on iOS.
///
/// Displays:
/// - Model selector with RAM-based auto-selection
/// - Active backend (Metal GPU / CPU)
/// - Real-time benchmark dashboard (prefill/decode tk/s)
/// - Streaming chat output
struct ContentView: View {
    @StateObject private var manager = LiteRTManager.shared
    @State private var inputText = ""
    @State private var outputLines: [String] = []
    @State private var streamingText = ""
    @State private var isExecuting = false
    @State private var prefillTkSec: Float = 0
    @State private var decodeTkSec: Float = 0
    @State private var lastInferenceMs: Int = 0
    @State private var selectedItem: PhotosPickerItem? = nil
    @State private var selectedImage: UIImage? = nil
    @State private var hasImageData: Data? = nil

    var body: some View {
        VStack(spacing: 12) {
            // Status header
            HStack(spacing: 8) {
                StatusChip(text: manager.isLoaded ? "Loaded" : "Not loaded",
                           color: manager.isLoaded ? .green : .gray)
                if manager.isLoaded {
                    StatusChip(text: manager.activeBackend, color: .blue)
                }
            }

            // Benchmark dashboard
            if lastInferenceMs > 0 {
                HStack(spacing: 16) {
                    Label("\(Int(prefillTkSec)) tk/s prefill", systemImage: "bolt.fill")
                        .font(.caption)
                        .foregroundColor(.accentColor)
                    Label(String(format: "%.1f tk/s decode", decodeTkSec), systemImage: "speedometer")
                        .font(.caption)
                        .foregroundColor(.accentColor)
                    Label("\(lastInferenceMs)ms", systemImage: "clock")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            // Model selector
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(LiteRTManager.PCOSModel.allCases, id: \.self) { model in
                        Button(action: { Task { try? await manager.loadModel(model) } }) {
                            Text(model.displayName)
                                .font(.caption)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(manager.currentModel == model ? Color.accentColor.opacity(0.2) : Color.gray.opacity(0.1))
                                .cornerRadius(16)
                        }
                    }
                }
            }

            // Device tier info
            Text("RAM: \(manager.totalRamMb)MB · Tier: \(manager.deviceTier.rawValue)")
                .font(.caption2)
                .foregroundColor(.secondary)

            // Output area
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(outputLines.indices, id: \.self) { i in
                            Text(outputLines[i])
                                .font(.system(.body, design: .monospaced))
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        if !streamingText.isEmpty {
                            Text(streamingText)
                                .font(.system(.body, design: .monospaced))
                                .foregroundColor(.accentColor)
                        }
                    }
                    .padding(.horizontal)
                }
                .onChange(of: outputLines.count) { _ in
                    proxy.scrollTo(outputLines.count - 1, anchor: .bottom)
                }
            }

            // PhotosPicker for multimodal input
            if manager.isVisionSupported() {
                HStack {
                    PhotosPicker(selection: $selectedItem, matching: .images) {
                        Label("Select Image", systemImage: "photo")
                            .font(.caption)
                    }
                    if selectedImage != nil {
                        Button(action: clearImage) {
                            Label("Clear", systemImage: "xmark.circle.fill")
                                .font(.caption)
                                .foregroundColor(.red)
                        }
                    }
                    if manager.isAudioSupported() {
                        Label("Audio Ready", systemImage: "mic.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                    }
                }
                .padding(.horizontal)

                // Image preview
                if let image = selectedImage {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 150)
                        .cornerRadius(8)
                        .padding(.horizontal)
                }
            }

            // Input
            HStack {
                TextField("Ask PCOS…", text: $inputText, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...4)

                Button(action: execute) {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title2)
                }
                .disabled(inputText.trimmingCharacters(in: .whitespaces).isEmpty || isExecuting || !manager.isLoaded)
            }
            .padding(.horizontal)
        }
        .padding()
        .task {
            // Auto-select and warm-load best model on startup
            let recommended = manager.recommendModelForDevice("chat")
            try? await manager.loadModel(recommended)
        }
        .onChange(of: selectedItem) { _, newItem in
            Task {
                if let item = newItem,
                   let data = try? await item.loadTransferable(type: Data.self),
                   let uiImage = UIImage(data: data) {
                    await MainActor.run {
                        selectedImage = uiImage
                        hasImageData = data
                        manager.selectedImageData = data
                    }
                }
            }
        }
    }

    private func clearImage() {
        selectedImage = nil
        hasImageData = nil
        selectedItem = nil
        manager.selectedImageData = nil
    }

    private func execute() {
        let input = inputText.trimmingCharacters(in: .whitespaces)
        guard !input.isEmpty, !isExecuting, manager.isLoaded else { return }

        isExecuting = true
        outputLines.append("→ \(input)")
        if hasImageData != nil {
            outputLines.append("  [image attached]")
        }
        streamingText = ""
        inputText = ""

        Task {
            let start = DispatchTime.now()

            do {
                let result: String
                if let imageData = hasImageData, manager.isVisionSupported() {
                    // Multimodal inference with image
                    result = await manager.inferStreamingWithImage(
                        prompt: input, imageData: imageData
                    ) { chunk in
                        streamingText += chunk
                    }
                } else {
                    // Text-only streaming inference
                    result = try await manager.inferStreaming(input) { chunk in
                        streamingText += chunk
                    }
                }

                let elapsed = DispatchTime.now().uptimeNanoseconds - start.uptimeNanoseconds
                let elapsedMs = Int(elapsed / 1_000_000)

                // Estimate tokens (~4 chars/token for English)
                let outputTokens = max(1, result.count / 4)
                let inputTokens = max(1, input.count / 4)
                let decode = Float(outputTokens) / Float(max(1, elapsedMs)) * 1000.0
                let prefill = Float(inputTokens) / Float(max(1, elapsedMs / 1000))

                await MainActor.run {
                    prefillTkSec = prefill
                    decodeTkSec = decode
                    lastInferenceMs = elapsedMs
                    outputLines.append("  \(result)")
                    outputLines.append("  ⚡ \(Int(prefill)) tk/s prefill, \(String(format: "%.1f", decode)) tk/s decode, \(elapsedMs)ms")
                    streamingText = ""
                    isExecuting = false
                }
            } catch {
                await MainActor.run {
                    outputLines.append("  Error: \(error.localizedDescription)")
                    isExecuting = false
                }
            }
        }
    }
}

// MARK: - Status Chip

struct StatusChip: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption2)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .cornerRadius(8)
    }
}
