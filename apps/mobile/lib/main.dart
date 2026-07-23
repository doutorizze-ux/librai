import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'presentation/screens/home_screen.dart';
import 'presentation/screens/translation_screen.dart';
import 'presentation/screens/dictionary_screen.dart';
import 'presentation/screens/conversation_screen.dart';
import 'presentation/screens/trainer_screen.dart';

void main() {
  runApp(
    const ProviderScope(
      child: SinalizaAiApp(),
    ),
  );
}

class SinalizaAiApp extends StatelessWidget {
  const SinalizaAiApp({super.key});

  @override
  Widget build(BuildContext context) {
    final GoRouter router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const HomeScreen(),
        ),
        GoRoute(
          path: '/translate',
          builder: (context, state) => const TranslationScreen(),
        ),
        GoRoute(
          path: '/dictionary',
          builder: (context, state) => const DictionaryScreen(),
        ),
        GoRoute(
          path: '/conversation',
          builder: (context, state) => const ConversationScreen(),
        ),
        GoRoute(
          path: '/trainer',
          builder: (context, state) => const TrainerScreen(),
        ),
      ],
    );

    return MaterialApp.router(
      title: 'LibrAI',
      debugShowCheckedModeBanner: false,
      themeMode: ThemeMode.system,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF8F7FC),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF4F378B),
          brightness: Brightness.light,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFF8F7FC),
          surfaceTintColor: Colors.transparent,
          centerTitle: true,
        ),
        cardTheme: const CardThemeData(
          elevation: 0,
          margin: EdgeInsets.zero,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            minimumSize: const Size(48, 56),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        ),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFD0BCFF),
          brightness: Brightness.dark,
        ),
      ),
      routerConfig: router,
    );
  }
}
