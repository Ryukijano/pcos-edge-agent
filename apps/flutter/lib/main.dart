import 'package:flutter/material.dart';
import 'litert_manager.dart';

void main() {
  runApp(const PCOSEdgeApp());
}

class PCOSEdgeApp extends StatelessWidget {
  const PCOSEdgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PCOS Edge',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      home: const ChatPage(),
    );
  }
}

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final LiteRTManager _manager = LiteRTManager();
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<String> _outputLines = [];
  String _streamingText = '';
  bool _isExecuting = false;

  @override
  void initState() {
    super.initState();
    _warmLoad();
  }

  Future<void> _warmLoad() async {
    final recommended = _manager.recommendModelForDevice();
    await _manager.loadModel(recommended);
  }

  Future<void> _execute() async {
    final input = _inputController.text.trim();
    if (input.isEmpty || _isExecuting || !_manager.isLoaded) return;

    setState(() {
      _isExecuting = true;
      _outputLines.add('→ $input');
      _streamingText = '';
      _inputController.clear();
    });

    try {
      final result = await _manager.inferStreaming(
        input,
        onChunk: (chunk) {
          setState(() {
            _streamingText += chunk;
          });
        },
      );

      setState(() {
        _outputLines.add('  $result');
        _outputLines.add(
          '  ⚡ TTFT: ${_manager.ttftMs}ms | '
          '${_manager.prefillTkSec.round()} tk/s prefill | '
          '${_manager.decodeTkSec.toStringAsFixed(1)} tk/s decode | '
          '${_manager.lastInferenceMs}ms total',
        );
        _streamingText = '';
        _isExecuting = false;
      });

      _scrollToBottom();
    } catch (e) {
      setState(() {
        _outputLines.add('  Error: $e');
        _isExecuting = false;
      });
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _manager.dispose();
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PCOS Edge'),
        actions: [
          Chip(
            label: Text(
              _manager.isLoaded ? _manager.activeBackend : 'Loading…',
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Benchmark dashboard
          if (_manager.lastInferenceMs > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  _MetricChip('TTFT: ${_manager.ttftMs}ms', Colors.orange),
                  _MetricChip(
                    '⚡ ${_manager.prefillTkSec.round()} tk/s prefill',
                    Theme.of(context).colorScheme.primary,
                  ),
                  _MetricChip(
                    '${_manager.decodeTkSec.toStringAsFixed(1)} tk/s decode',
                    Theme.of(context).colorScheme.primary,
                  ),
                  _MetricChip(
                    '${_manager.lastInferenceMs}ms',
                    Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),

          // Device tier info
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Text(
              'RAM: ${_manager.totalRamMb}MB · Tier: ${_manager.deviceTier.name}',
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ),

          // Model selector
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: PCOSModel.values.map((model) {
                final selected = _manager.currentModel == model;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: FilterChip(
                    label: Text(model.displayName),
                    selected: selected,
                    onSelected: (_) => _manager.loadModel(model),
                  ),
                );
              }).toList(),
            ),
          ),

          // Output area
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _outputLines.length + (_streamingText.isNotEmpty ? 1 : 0),
              itemBuilder: (context, index) {
                if (index < _outputLines.length) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      _outputLines[index],
                      style: index % 2 == 0
                          ? Theme.of(context).textTheme.bodyMedium
                          : Theme.of(context).textTheme.bodySmall?.copyWith(
                                fontFamily: 'monospace',
                                color: Theme.of(context).colorScheme.onSurfaceVariant,
                              ),
                    ),
                  );
                }
                return Text(
                  _streamingText,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.primary,
                    fontFamily: 'monospace',
                  ),
                );
              },
            ),
          ),

          // Input
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _inputController,
                    maxLines: null,
                    decoration: const InputDecoration(
                      hintText: 'Ask PCOS…',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _execute(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  icon: const Icon(Icons.send),
                  onPressed: _isExecuting ? null : _execute,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricChip extends StatelessWidget {
  final String label;
  final Color color;
  const _MetricChip(this.label, this.color);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Text(label, style: TextStyle(fontSize: 11, color: color)),
    );
  }
}
