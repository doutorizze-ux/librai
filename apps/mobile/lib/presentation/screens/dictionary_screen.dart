import 'package:flutter/material.dart';

class DictionaryEntry {
  final String title;
  final String category;
  final String description;
  final String steps;

  DictionaryEntry({
    required this.title,
    required this.category,
    required this.description,
    required this.steps,
  });
}

class DictionaryScreen extends StatefulWidget {
  const DictionaryScreen({super.key});

  @override
  State<DictionaryScreen> createState() => _DictionaryScreenState();
}

class _DictionaryScreenState extends State<DictionaryScreen> {
  final List<DictionaryEntry> _allEntries = [
    DictionaryEntry(
      title: "AJUDA",
      category: "Emergência",
      description: "Sinal solicitando auxílio ou assistência imediata.",
      steps: "Mão esquerda espalmada, virada para cima. Mão direita fechada com polegar estendido para cima bate levemente sobre a palma da mão esquerda.",
    ),
    DictionaryEntry(
      title: "EMERGÊNCIA",
      category: "Emergência",
      description: "Indicação de perigo imediato ou necessidade médica crítica.",
      steps: "Mão em formato de garra faz movimentos rápidos circulares na altura do peito, expressando urgência no semblante.",
    ),
    DictionaryEntry(
      title: "SAÚDE",
      category: "Saúde",
      description: "Referência a bem-estar físico, medicina ou consulta médica.",
      steps: "Dedos médio e anelar curvados tocam de leve os lados esquerdo e direito do peito alternadamente.",
    ),
    DictionaryEntry(
      title: "BOM_DIA",
      category: "Cumprimentos",
      description: "Saudação matinal padrão.",
      steps: "Mão direita fechada próxima à boca abre-se em formato de 'copo' (sinal de BOM). Em seguida, com a mão direita em formato de semi-círculo, eleva-se simulando o nascer do sol (sinal de DIA).",
    ),
    DictionaryEntry(
      title: "HOSPITAL",
      category: "Saúde",
      description: "Referência à instituição de saúde ou internação.",
      steps: "Dedo indicador da mão direita traça o sinal de uma cruz na testa ou no braço esquerdo.",
    ),
  ];

  String _searchQuery = "";
  String _selectedCategory = "Todos";

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // Filtragem dos sinais
    final filteredEntries = _allEntries.where((entry) {
      final matchesSearch = entry.title.toLowerCase().contains(_searchQuery.toLowerCase()) ||
                            entry.description.toLowerCase().contains(_searchQuery.toLowerCase());
      final matchesCategory = _selectedCategory == "Todos" || entry.category == _selectedCategory;
      return matchesSearch && matchesCategory;
    }).toList();

    final categories = ["Todos", "Emergência", "Saúde", "Cumprimentos"];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dicionário de Libras'),
      ),
      body: Column(
        children: [
          // Barra de Busca
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: TextField(
              decoration: InputDecoration(
                hintText: 'Pesquise por termos...',
                prefixIcon: const Icon(Icons.search),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                contentPadding: const EdgeInsets.symmetric(vertical: 0),
              ),
              onChanged: (val) {
                setState(() {
                  _searchQuery = val;
                });
              },
            ),
          ),

          // Chips de Categoria
          SizedBox(
            height: 48,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: categories.length,
              itemBuilder: (context, index) {
                final cat = categories[index];
                final isSelected = _selectedCategory == cat;
                return Padding(
                  padding: const EdgeInsets.only(right: 8.0),
                  child: FilterChip(
                    label: Text(cat),
                    selected: isSelected,
                    onSelected: (val) {
                      setState(() {
                        _selectedCategory = cat;
                      });
                    },
                    selectedColor: theme.colorScheme.primaryContainer,
                  ),
                );
              },
            ),
          ),

          const SizedBox(height: 8),

          // Lista de Termos Filtrados
          Expanded(
            child: filteredEntries.isEmpty
                ? const Center(child: Text('Nenhum sinal encontrado para esta pesquisa.'))
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: filteredEntries.length,
                    itemBuilder: (context, index) {
                      final entry = filteredEntries[index];

                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: ExpansionTile(
                          leading: Icon(
                            entry.category == "Emergência" 
                              ? Icons.warning_amber_rounded 
                              : entry.category == "Saúde" 
                                ? Icons.local_hospital 
                                : Icons.handshake,
                            color: entry.category == "Emergência" ? Colors.redAccent : theme.colorScheme.primary,
                          ),
                          title: Text(
                            entry.title,
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                          subtitle: Text(entry.category),
                          children: [
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    entry.description,
                                    style: theme.textTheme.bodyMedium?.copyWith(
                                      color: theme.colorScheme.onSurfaceVariant,
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  const Text(
                                    'Como fazer o sinal:',
                                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                                  ),
                                  const SizedBox(height: 4),
                                  // Semântica detalhada para TalkBack/VoiceOver
                                  Semantics(
                                    label: 'Passo a passo do sinal: ${entry.steps}',
                                    child: Text(
                                      entry.steps,
                                      style: theme.textTheme.bodySmall?.copyWith(
                                        fontStyle: FontStyle.italic,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                ],
                              ),
                            )
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
