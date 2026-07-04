import 'dart:io';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:flutter_litert_lm/flutter_litert_lm.dart';

/// Device RAM tier for model auto-selection.
enum DeviceTier { lowEnd, midRange, highEnd }

/// PCOS model definitions matching the Android/iOS apps.
enum PCOSModel {
  functionGemma('FunctionGemma 270M (CPU)', 'functiongemma-270m-ft-mobile-actions.litertlm', 289),
  gemma4E2B('Gemma 4 E2B 2.3B (GPU)', 'gemma-4-E2B-it.litertlm', 2583),
  gemma4E4B('Gemma 4 E4B 4.5B (GPU)', 'gemma-4-E4B-it.litertlm', 3654),
  gemma4E2BMobile('Gemma 4 E2B Mobile 1GB (QAT)', 'gemma-4-E2B-it-mobile.litertlm', 1100),
  gemma4E4BMobile('Gemma 4 E4B Mobile 2.2GB (QAT)', 'gemma-4-E4B-it-mobile.litertlm', 2200);

  final String displayName;
  final String fileName;
  final int sizeMb;
  const PCOSModel(this.displayName, this.fileName, this.sizeMb);
}

/// LiteRT-LM Manager — handles engine lifecycle, model loading, and streaming inference.
///
/// Uses flutter_litert_lm (community package) for cross-platform support:
/// iOS (Metal), Android (OpenCL/NPU), macOS, Windows, Linux.
class LiteRTManager extends ChangeNotifier {
  LiteLmEngine? _engine;
  LiteLmConversation? _conversation;
  PCOSModel? _currentModel;
  String _activeBackend = 'unknown';
  bool _isLoaded = false;
  bool _isLoading = false;

  // Benchmark metrics
  double _prefillTkSec = 0;
  double _decodeTkSec = 0;
  int _ttftMs = 0;
  int _lastInferenceMs = 0;

  bool get isLoaded => _isLoaded;
  bool get isLoading => _isLoading;
  PCOSModel? get currentModel => _currentModel;
  String get activeBackend => _activeBackend;
  double get prefillTkSec => _prefillTkSec;
  double get decodeTkSec => _decodeTkSec;
  int get ttftMs => _ttftMs;
  int get lastInferenceMs => _lastInferenceMs;

  /// Detect device RAM in MB.
  /// On mobile, uses ProcessInfo; on desktop, uses Platform-specific methods.
  int get totalRamMb {
    if (Platform.isIOS || Platform.isMacOS) {
      // Apple devices: use NSProcessInfo via FFI or platform channel
      // For now, estimate based on device model
      return 8192; // Default for modern Apple devices
    } else if (Platform.isAndroid) {
      // Android: parse /proc/meminfo
      try {
        final meminfo = File('/proc/meminfo').readAsStringSync();
        final match = RegExp(r'MemTotal:\s+(\d+)').firstMatch(meminfo);
        if (match != null) {
          return int.parse(match.group(1)!) ~/ 1024;
        }
      } catch (_) {}
      return 6144; // Default
    }
    return 8192; // Desktop default
  }

  /// Classify device into tier based on RAM.
  DeviceTier get deviceTier {
    final ram = totalRamMb;
    if (ram >= 8192) return DeviceTier.highEnd;
    if (ram >= 6144) return DeviceTier.midRange;
    return DeviceTier.lowEnd;
  }

  /// Recommend best model for this device.
  PCOSModel recommendModelForDevice({String taskType = 'chat'}) {
    switch (deviceTier) {
      case DeviceTier.lowEnd:
        return taskType == 'action' ? PCOSModel.functionGemma : PCOSModel.gemma4E2BMobile;
      case DeviceTier.midRange:
        if (taskType == 'action') return PCOSModel.functionGemma;
        if (taskType == 'reasoning') return PCOSModel.gemma4E4BMobile;
        return PCOSModel.gemma4E2B;
      case DeviceTier.highEnd:
        if (taskType == 'action') return PCOSModel.functionGemma;
        if (taskType == 'reasoning' || taskType == 'multimodal') return PCOSModel.gemma4E4B;
        return PCOSModel.gemma4E2B;
    }
  }

  /// Load a model into the LiteRT-LM engine.
  Future<void> loadModel(PCOSModel model) async {
    if (_currentModel == model && _engine != null) return;

    _isLoading = true;
    notifyListeners();

    try {
      _conversation?.dispose();
      _engine?.dispose();

      // Configure engine with GPU backend for Gemma 4 models
      final config = LiteLmEngineConfig(
        modelPath: model.fileName,
        backend: model == PCOSModel.functionGemma ? Backend.cpu : Backend.gpu,
        maxTokens: 8192,
      );

      _engine = await LiteLmEngine.create(config);
      _conversation = _engine!.createConversation();

      _currentModel = model;
      _activeBackend = model == PCOSModel.functionGemma ? 'CPU' : 'GPU';
      _isLoaded = true;
    } catch (e) {
      debugPrint('Failed to load model: $e');
      _isLoaded = false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Streaming inference with benchmark tracking.
  Future<String> inferStreaming(String prompt, {void Function(String)? onChunk}) async {
    if (_conversation == null) throw Exception('Engine not loaded');

    final stopwatch = Stopwatch()..start();
    int firstTokenMs = 0;
    final buffer = StringBuffer();

    await for (final chunk in _conversation!.sendMessageStreaming(prompt)) {
      if (firstTokenMs == 0) {
        firstTokenMs = stopwatch.elapsedMilliseconds;
      }
      buffer.write(chunk);
      onChunk?.call(chunk);
    }

    stopwatch.stop();
    final elapsedMs = stopwatch.elapsedMilliseconds;
    final ttft = firstTokenMs > 0 ? firstTokenMs : elapsedMs;

    // Estimate tokens (~4 chars/token)
    final outputTokens = max(1, buffer.length ~/ 4);
    final inputTokens = max(1, prompt.length ~/ 4);
    final decode = elapsedMs > 0 ? (outputTokens / elapsedMs * 1000) : 0.0;
    final prefill = elapsedMs > 0 ? (inputTokens / (elapsedMs / 1000)) : 0.0;

    _prefillTkSec = prefill;
    _decodeTkSec = decode;
    _ttftMs = ttft;
    _lastInferenceMs = elapsedMs;
    notifyListeners();

    return buffer.toString();
  }

  /// Cancel ongoing generation.
  void cancel() {
    _conversation?.cancel();
  }

  /// Clean up resources.
  void dispose() {
    _conversation?.dispose();
    _engine?.dispose();
    _isLoaded = false;
    super.dispose();
  }
}
