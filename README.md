# SmartBPO 💼🚀

Um assistente de produtividade desktop desenvolvido em Python focado em automatizar, organizar e otimizar o fluxo de trabalho diário de analistas de BPO Financeiro e equipes de suporte.

O SmartBPO unifica ferramentas vitais em uma única interface *flat* e moderna, eliminando tarefas repetitivas e trazendo gamificação para as metas de atendimento.

---

## ✨ Principais Funcionalidades

* ⚡ **Devolutivas (Macros Automáticas):** Gerenciador de perfis de respostas rápidas. Salve textos longos e utilize atalhos globais de teclado (ex: `Ctrl+1` a `Ctrl+9`) para colar o conteúdo instantaneamente em qualquer janela do sistema operativo. Inclui atalhos dedicados para colar "CPF: " e "CNPJ: ".
* 🔗 **Hub de Consultas:** Gerenciador de links favoritos com suporte a duplo clique para acesso rápido a sistemas frequentes (Plataforma Senior, Receita Federal, Simples Nacional, etc).
* 🧮 **Calculadora Avançada:**
    * *Padrão:* Uma calculadora segura (parseamento via `ast`, protegida contra injeções de código) com histórico contínuo em janela pop-up.
    * *Simples Nacional:* Ferramenta de negócio integrada para cálculo exato da Base de Cálculo e Média Móvel, com suporte a cenários de empresas com mais ou menos de 12 meses de operação (RBT12, RPA, PAA).
* 📊 **Dashboard de Volumetria:** Acompanhamento de metas com gamificação. Defina metas "PRO" (qualidade) e "PREMIUM" (premiação). Inclui um contador de fluxo em tempo real e cálculo inteligente de média diária necessária para bater a meta do mês (descontando fins de semana).
* 📝 **Anotações (Rich Text):** Espaço para anotações rápidas com salvamento automático em *background*, suporte a formatação (negrito, itálico) e alinhamentos.
* 📅 **Agenda & Lembretes:** Gestão de compromissos únicos e diários (Daily) com sistema de notificação via pop-ups *always-on-top* (alertas aos 10 minutos restantes e no momento exato).

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.x
* **Interface Gráfica:** `tkinter` com `ttk` (Estilização *clam* customizada)
* **Automação & SO:** * `pyautogui` (Automação de colagem)
    * `keyboard` (Escuta de atalhos globais)
    * `pyperclip` (Manipulação da área de transferência)
* **Persistência de Dados:** Arquivos `.json` nativos (armazenamento local *offline-first*).

---

## ⚙️ Pré-requisitos e Instalação

Certifique-se de ter o Python 3 instalado em sua máquina.

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/SEU_USUARIO/SmartBPO.git](https://github.com/SEU_USUARIO/SmartBPO.git)
   cd SmartBPO
