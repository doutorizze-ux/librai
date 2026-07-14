import sys
import os

# Adiciona o diretório raiz ao path para encontrar a pasta 'ml'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ml.evaluation.linguistic_metrics import (
    calculate_wer,
    calculate_bleu,
    calculate_ser,
    evaluate_translation_performance
)

def test_wer_calculation():
    # Caso 1: Sentenças idênticas
    assert calculate_wer("Eu preciso de ajuda", "Eu preciso de ajuda") == 0.0

    # Caso 2: Uma exclusão (1/4 = 0.25)
    assert calculate_wer("Eu preciso de ajuda", "Eu preciso ajuda") == 0.25

    # Caso 3: Uma inserção (1/4 = 0.25)
    assert calculate_wer("Eu preciso de ajuda", "Eu preciso de muita ajuda") == 0.25

    # Caso 4: Uma substituição (1/4 = 0.25)
    assert calculate_wer("Eu preciso de ajuda", "Eu quero de ajuda") == 0.25


def test_ser_calculation():
    # Caso 1: Sinais idênticos
    assert calculate_ser(["AJUDA", "SAÚDE"], ["AJUDA", "SAÚDE"]) == 0.0

    # Caso 2: Um sinal deletado (1/2 = 0.5)
    assert calculate_ser(["AJUDA", "SAÚDE"], ["AJUDA"]) == 0.5


def test_bleu_calculation():
    # Caso 1: Alta similaridade
    bleu_high = calculate_bleu("eu preciso ir ao hospital rápido", "eu preciso ir hospital rápido")
    # Caso 2: Baixa similaridade
    bleu_low = calculate_bleu("eu preciso ir ao hospital rápido", "hoje o dia está muito chuvoso")
    
    assert bleu_high > bleu_low
    assert 0.0 <= bleu_high <= 1.0


def test_performance_compilation():
    results = evaluate_translation_performance("preciso de médico", "preciso de médico")
    assert results["word_error_rate"] == 0.0
    assert results["sentence_match"] is True
