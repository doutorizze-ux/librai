import math
from collections import Counter

def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Calcula o Word Error Rate (WER) baseado na distância de Levenshtein entre palavras.
    """
    ref_words = reference.strip().lower().split()
    hyp_words = hypothesis.strip().lower().split()

    if not ref_words:
        if hyp_words:
            return float(len(hyp_words))
        return 0.0

    # Inicializar matriz Levenshtein
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                substitution = d[i - 1][j - 1] + 1
                insertion = d[i][j - 1] + 1
                deletion = d[i - 1][j] + 1
                d[i][j] = min(substitution, insertion, deletion)

    # Distância total dividida pelo tamanho da referência
    return d[len(ref_words)][len(hyp_words)] / len(ref_words)


def calculate_ser(reference_signs: list, hypothesis_signs: list) -> float:
    """
    Calcula o Sign Error Rate (SER) - taxa de erro de sinais isolados/glóssas.
    """
    if not reference_signs:
        return 1.0 if hypothesis_signs else 0.0
        
    ref_str = " ".join(reference_signs)
    hyp_str = " ".join(hypothesis_signs)
    return calculate_wer(ref_str, hyp_str)


def _get_ngrams(words, n):
    return [tuple(words[i:i+n]) for i in range(len(words)-n+1)]


def calculate_bleu(reference: str, hypothesis: str) -> float:
    """
    Cálculo simplificado do BLEU-4 nativo (sem dependência do NLTK).
    Retorna um float de 0.0 a 1.0.
    """
    ref_words = reference.strip().lower().split()
    hyp_words = hypothesis.strip().lower().split()
    
    if not hyp_words or not ref_words:
        return 0.0

    precisions = []
    for n in range(1, 5): # 1-gram a 4-gram
        ref_ngrams = _get_ngrams(ref_words, n)
        hyp_ngrams = _get_ngrams(hyp_words, n)
        
        if not hyp_ngrams:
            precisions.append(0.0)
            continue
            
        ref_counts = Counter(ref_ngrams)
        hyp_counts = Counter(hyp_ngrams)
        
        # Interseção clipada pelas contagens da referência
        overlap = 0
        for ngram, count in hyp_counts.items():
            overlap += min(count, ref_counts.get(ngram, 0))
            
        precisions.append(overlap / len(hyp_ngrams))

    # Se qualquer precisão de n-gram for zero, o BLEU-4 puro com média geométrica zera.
    # Para evitar zerar por frases curtas sem 4-gram, suavizamos somando pequena constante.
    smoothed_precisions = []
    for i, p in enumerate(precisions):
        if p == 0:
            smoothed_precisions.append(0.1 / (i + 1))
        else:
            smoothed_precisions.append(p)
            
    # Média geométrica
    geom_mean = math.exp(sum(math.log(p) for p in smoothed_precisions) / 4)
    
    # Brevity Penalty (BP)
    c = len(hyp_words)
    r = len(ref_words)
    if c > r:
        bp = 1.0
    else:
        bp = math.exp(1 - r / c) if c > 0 else 0.0
        
    return bp * geom_mean


def evaluate_translation_performance(reference: str, hypothesis: str) -> dict:
    """
    Retorna um dicionário compilando todas as métricas linguísticas do par.
    """
    wer = calculate_wer(reference, hypothesis)
    bleu = calculate_bleu(reference, hypothesis)
    
    return {
        "word_error_rate": round(wer, 4),
        "bleu_4": round(bleu, 4),
        "sentence_match": reference.strip().lower() == hypothesis.strip().lower()
    }


if __name__ == "__main__":
    # Teste rápido
    ref = "eu preciso ir ao hospital rápido"
    hyp = "eu preciso ir hospital rápido"
    print("Métricas de Teste:")
    print(evaluate_translation_performance(ref, hyp))
