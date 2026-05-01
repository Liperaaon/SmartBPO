# SmartBPO 💼🚀

O **SmartBPO** é um assistente de produtividade desktop desenvolvido em Python, focado em automatizar, organizar e otimizar o fluxo de trabalho diário de analistas de BPO Financeiro e equipas de suporte. 

Esta ferramenta foi construída para unificar funcionalidades vitais numa única interface moderna, eliminando tarefas repetitivas e trazendo gamificação para as metas de atendimento.

---

## ✨ Principais Funcionalidades

* ⚡ **Devolutivas (Macros Automáticas):** Gestor de perfis de respostas rápidas. Guarda textos longos e utiliza atalhos globais de teclado (ex: `Ctrl+1` a `Ctrl+9`) para colar o conteúdo instantaneamente em qualquer janela, poupando tempo em atendimentos repetitivos.
* 🔗 **Hub de Consultas:** Gestor de links favoritos com suporte a duplo clique para acesso rápido a sistemas frequentes (Plataforma Senior, Receita Federal, Simples Nacional, etc).
* 🧮 **Calculadora Avançada:**
    * *Padrão:* Calculadora segura (parseamento via `ast`) com histórico de cálculos em janela pop-up.
    * *Simples Nacional:* Ferramenta de negócio integrada para cálculo de Base de Cálculo e Média Móvel, com suporte a cenários de empresas com mais ou menos de 12 meses de operação.
* 📊 **Dashboard de Volumetria:** Acompanhamento de metas com gamificação. Define metas "PRO" (qualidade) e "PREMIUM" (premiação). Inclui um contador de fluxo em tempo real e cálculo inteligente de média diária necessária para bater a meta do mês.
* 📝 **Anotações (Rich Text):** Espaço para notas rápidas com salvamento automático, suporte a formatação (negrito, itálico) e alinhamentos.
* 📅 **Agenda & Lembretes:** Gestão de compromissos únicos e recorrentes (Daily) com sistema de notificação via pop-ups *always-on-top* (alertas aos 10 minutos e no momento exato).

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.x
* **Interface Gráfica:** `tkinter` com `ttk` (Estilização customizada com foco em UX)
* **Automação:** * `pyautogui` (Automação de interface)
    * `keyboard` (Gatilhos de atalhos globais)
    * `pyperclip` (Manipulação de área de transferência)
* **Persistência:** Arquivos `.json` nativos (armazenamento local *offline-first*).

---

## ⚙️ Instalação e Execução

Certifica-te de que tens o Python 3 instalado.

1. **Clonar o repositório:**
   ```bash
   git clone [https://github.com/teu-usuario/SmartBPO.git](https://github.com/teu-usuario/SmartBPO.git)
   cd SmartBPO
