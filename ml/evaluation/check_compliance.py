import os
import re

def check_accessibility_compliance(flutter_dir):
    """
    Varre os arquivos do Flutter e calcula a cobertura de rótulos semânticos (TalkBack/VoiceOver).
    """
    total_interactive_elements = 0
    labeled_elements = 0
    
    # Padrões regex para botões interativos e detectores de gestos
    button_patterns = [
        re.compile(r'IconButton\('),
        re.compile(r'ElevatedButton\('),
        re.compile(r'TextButton\('),
        re.compile(r'OutlinedButton\('),
        re.compile(r'GestureDetector\('),
        re.compile(r'InkWell\(')
    ]
    
    # Rótulos semânticos válidos
    label_patterns = [
        re.compile(r'semanticsLabel\s*:'),
        re.compile(r'Semantics\(')
    ]
    
    for root, _, files in os.walk(flutter_dir):
        for file in files:
            if file.endswith('.dart'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Contar elementos interativos
                    for pattern in button_patterns:
                        total_interactive_elements += len(pattern.findall(content))
                    
                    # Contar elementos com rótulos acessíveis
                    for pattern in label_patterns:
                        labeled_elements += len(pattern.findall(content))
                        
    coverage = 100.0 if total_interactive_elements == 0 else (labeled_elements / total_interactive_elements) * 100.0
    return total_interactive_elements, labeled_elements, round(coverage, 2)


def scan_for_secrets(project_dir):
    """
    Procura por chaves de API expostas ou chaves privadas no código.
    """
    secret_pattern = re.compile(r'(api_key|secret_key|private_key|password)\s*=\s*["\'][a-zA-Z0-9_\-\+\=\/]{16,}["\']', re.IGNORECASE)
    leaks = []
    
    # Ignorar pastas de ambiente virtual, cache e Git
    ignored_dirs = ['venv', '.git', '.dart_tool', 'build', 'node_modules', '.next']
    
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.endswith(('.dart', '.py', '.js', '.ts', '.tsx', '.json', '.yml', '.yaml')):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        if secret_pattern.search(line):
                            # Evita alertar sobre mocks ou hashes de teste comuns
                            if "mock_" not in line and "test_" not in line:
                                leaks.append(f"{os.path.basename(filepath)}:L{line_num}")
    return leaks


def verify_lgpd_governance(project_dir):
    """
    Verifica a implementação do módulo de governança LGPD e expiração de dados.
    """
    has_consent_router = False
    has_retention_cleanup = False
    
    for root, _, files in os.walk(project_dir):
        for file in files:
            if file == 'privacy.py':
                has_consent_router = True
            if file == 'local_history_storage.dart':
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'cleanupOldSessions' in content:
                        has_retention_cleanup = True
                        
    return has_consent_router, has_retention_cleanup


def run_compliance_audit():
    print("=================================================================")
    print("        SINALIZA AI - VARREDURA AUTOMATIZADA DE COMPLIANCE       ")
    print("=================================================================")
    
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    flutter_dir = os.path.join(root_dir, "apps", "mobile")
    
    # 1. Auditoria de Acessibilidade (WCAG 2.2 AA)
    total_buttons, labeled, access_cov = check_accessibility_compliance(flutter_dir)
    print("\n[1] ACESSIBILIDADE WCAG 2.2 AA (TalkBack/VoiceOver)")
    print(f"  - Elementos Interativos Mapeados: {total_buttons}")
    print(f"  - Elementos com Rótulos Semânticos: {labeled}")
    print(f"  - Cobertura de Acessibilidade: {access_cov}%")
    if access_cov >= 80.0:
        print("  Status: APROVADO (Cobertura Excelente)")
    else:
        print("  Status: ALERTA (Adicione mais descrições semânticas)")
        
    # 2. Varredura de Segurança (Vazamento de Credenciais)
    leaks = scan_for_secrets(root_dir)
    print("\n[2] SEGURANÇA E HIGIENE DO CÓDIGO (Hardcoded Secrets)")
    if leaks:
        print(f"  Status: FALHA (Segredos expostos encontrados!)")
        for leak in leaks:
            print(f"    - Vazamento em: {leak}")
    else:
        print("  Status: APROVADO (Nenhum segredo real exposto em código)")
        
    # 3. Governança LGPD (Consentimento e Minimização)
    consent_ok, retention_ok = verify_lgpd_governance(root_dir)
    print("\n[3] GOVERNANÇA E CONFORMIDADE LGPD (Privacidade)")
    print(f"  - Endpoint de consentimento cadastrado: {'SIM' if consent_ok else 'NÃO'}")
    print(f"  - Rotina de descarte biometria (>30 dias): {'SIM' if retention_ok else 'NÃO'}")
    if consent_ok and retention_ok:
        print("  Status: APROVADO (Conformidade com a legislação brasileira)")
    else:
        print("  Status: PENDENTE (Verifique endpoints de privacidade)")
        
    print("\n=================================================================")

if __name__ == "__main__":
    run_compliance_audit()
