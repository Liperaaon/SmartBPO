import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
from tkinter import font as tkFont # Importação necessária para criar a fonte
import pyautogui
import keyboard
import threading
import time
import json
import os
import webbrowser
import math
import calendar
from datetime import date, datetime, timedelta
# from tkcalendar import Calendar # REMOVIDO: Substituído por simpledialog para evitar problemas de foco/toplevel
import re 
import ast 
import pyperclip 
from pathlib import Path
import operator # Adicionado para avaliação segura

# --- Configurações de Arquivo e Formato ---
# ALTERADO: Define o diretório de dados na pasta Documentos do usuário
try:
    # Usa a pasta Documentos do usuário atual
    DATA_DIR = Path(os.path.expanduser('~')) / 'Documents' / 'SmartBPO_Data'
    # Cria o diretório se não existir
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    # Fallback para o diretório de execução em caso de erro
    print(f"Erro ao criar DATA_DIR em Documentos: {e}. Usando diretório local.")
    DATA_DIR = Path('.')

def get_data_path(filename):
    """Retorna o caminho completo para o arquivo dentro do DATA_DIR."""
    return DATA_DIR / filename
    
# ARQUIVO DEVOLUTIVAS AGORA SÓ GUARDA QUAL PERFIL ESTÁ ATIVO
ARQUIVO_DEVOLUTIVAS_CONFIG = get_data_path("devolutivas_config.json")
ARQUIVO_LINKS = get_data_path("links_salvos.json")
ARQUIVO_VOLUMETRIA = get_data_path("volumetria.json")
ARQUIVO_CALCULADORA = get_data_path("calculadora_dados.json") 
ARQUIVO_AGENDAS = get_data_path("agendas_salvas.json") 
ARQUIVO_CONFIG = get_data_path("config.json") 
ARQUIVO_FLAG_INIT = get_data_path("init_flag.db") 
# NOVO ARQUIVO: Para anotações gerais
ARQUIVO_ANOTACOES = get_data_path("anotacoes_gerais.json") 

def get_profile_filepath(profile_name):
    """Retorna o caminho completo para o arquivo JSON de um perfil específico."""
    return DATA_DIR / f"macros_{profile_name.replace(' ', '_')}.json"

# FORMATOS
DATA_FORMATO_CURTO = '%d/%m' 
DATA_DISPLAY_CURTO = "DD/MM (Ex: 25/10)"
DATA_FORMATO_LONGO_PERSIST = '%d/%m/%Y' 
DATA_FORMATO_LONGO_ANTIGO = '%d-%m-%Y'
HORA_FORMATO = '%H:%M'
HORA_DISPLAY = "HH:MM (Ex: 09:30)"

# --- Constantes de Estilo ---
PRIMARY_BLUE = "#004494" # Azul Sicoob
LIGHT_BLUE = "#E6F0FF"   # Azul Claro (Fundo)
DANGER_RED = "#b00020"
SUCCESS_GREEN = "#006400"
BACKGROUND_GRAY = "#F8F8F8" # Fundo geral
STATUS_BAR_BG = "#EFEFEF"   # Fundo da barra de status

# --- Mapeamento de Ícones para Links ---
LINK_ICONS = {
    "senior": "🔑",
    "receita": "🔎",
    "simples": "📄",
    "validar": "✍️",
    "geral": "🌐"
}

# --- Funções de Avaliação Segura (Substitui o eval inseguro) ---

_OP_MAP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos
}

def safe_eval(node):
    """
    Avalia a expressão de forma segura, permitindo apenas operações matemáticas básicas.
    Rejeita chamadas de função, variáveis e outros elementos perigosos.
    """
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Expression):
        return safe_eval(node.body)
    elif isinstance(node, ast.BinOp):
        op = _OP_MAP.get(type(node.op))
        if op is None:
            raise TypeError(f"Operador binário não suportado: {type(node.op).__name__}")
        return op(safe_eval(node.left), safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = _OP_MAP.get(type(node.op))
        if op is None:
            raise TypeError(f"Operador unário não suportado: {type(node.op).__name__}")
        return op(safe_eval(node.operand))
    elif isinstance(node, ast.Call) or isinstance(node, ast.Name):
        # Bloqueia chamadas de função e variáveis (ex: 'import os')
        raise TypeError(f"Funções ou variáveis não são permitidas na calculadora: {type(node).__name__}")
    else:
        # Rejeita qualquer outro nó que não seja um literal ou operação básica
        raise TypeError(f"Elemento inválido na expressão: {type(node).__name__}")

# --- Classe Principal do Aplicativo ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("SmartBPO")
        self.geometry("900x680")
        # Altura mínima ajustada para garantir visibilidade da barra de status em notebooks
        self.minsize(850, 400) 
        
        self.app_rodando = True
        self.thread_atalhos = None
        self.thread_agendas = None
        self.popup_hints = None  
        self.reminder_popup = None 
        self.config_window = None 
        # REMOVIDO: calendar_popup não é mais um objeto Toplevel, mas mantemos None por segurança
        self.calendar_popup = None
        self.macro_feedback_popup = None
        self.metas_window = None # Janela de Metas
        self.standard_calc_window = None # Nova variável para a janela pop-up

        self._initialize_state_variables()
        
        self.configurar_estilos() 
        self.criar_menu_bar()

        self.carregar_dados_iniciais() 
        
        self.after(50, self._start_gui_and_tasks)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def get_total_working_days_in_month(self):
        """Calcula o número total de dias úteis (Seg-Sex) no mês atual."""
        hoje = date.today()
        # Obtém o último dia do mês
        _, total_days_in_month = calendar.monthrange(hoje.year, hoje.month)
        
        working_days = 0
        for day in range(1, total_days_in_month + 1):
            if date(hoje.year, hoje.month, day).weekday() < 5: 
                working_days += 1
        return working_days

    def _get_first_name(self):
        """Retorna apenas o primeiro nome do usuário, capitalizado, ou vazio."""
        name = self.user_name_var.get().strip()
        if not name:
            return ""
        # Retorna o primeiro nome com a primeira letra em maiúsculo
        return name.split(' ')[0].capitalize()

    def _start_gui_and_tasks(self):
        """Método seguro para iniciar a construção da GUI e tarefas assíncronas."""
        
        if not self.user_name_var.get(): 
             self.show_initial_setup()
        else:
             self.criar_widgets_principais()
             self._iniciar_tarefas_assincronas()


    def _iniciar_tarefas_assincronas(self):
        """Inicia todas as threads e chamadas de tempo que dependem dos métodos da classe."""
        self.iniciar_thread_atalhos() 
        self.iniciar_thread_verificacao_agendas()
        self.update_time() 

        
    def atualizar_status(self, mensagem, tempo_ms=3000):
        """Atualiza a barra de status e limpa após um tempo."""
        if hasattr(self, 'status_var') and self.status_var:
            self.status_var.set(mensagem)
            if tempo_ms > 0:
                self.after(tempo_ms, lambda: self.status_var.set("Pronto."))
        
    def _initialize_state_variables(self):
        """Inicializa todas as variáveis de estado do aplicativo."""
        self.status_var = tk.StringVar(value="Pronto.")
        self.time_var = tk.StringVar(value="") 
        self.next_agenda_var = tk.StringVar(value="Próxima Agenda: N/A") 
        
        # Devolutivas agora são gerenciadas por perfil
        self.devolutivas_contents = [tk.StringVar() for _ in range(9)]
        self.devolutivas_text_widgets = [] 
        
        # O self.devolutivas_profiles agora é apenas uma lista de NOMES
        self.devolutivas_profiles = [] 
        self.devolutivas_active_profile_name = tk.StringVar(value="Personalizada") # Nome do perfil ativo
        
        self.links_data = []
        self.volumetria_data = []
        self.agendas_data = [] 
        
        self.calc_display_var = tk.StringVar()
        self.cenario_var = tk.StringVar(value=">12m")
        self.simples_rbt12_var = tk.StringVar()
        self.simples_rpa_var = tk.StringVar()
        self.simples_paa_var = tk.StringVar()
        self.simples_total_acumulado_var = tk.StringVar()
        self.simples_meses_var = tk.StringVar()
        
        self.res1_var = tk.StringVar()
        self.res2_var = tk.StringVar()
        self.res3_var = tk.StringVar()
        self.resultados_vars = {"res1": self.res1_var, "res2": self.res2_var, "res3": self.res3_var}
        self.calc_history = []
        # REMOVIDO: calc_notes_var (anotações da calculadora) -> SUBSTITUÍDO por anotacoes_gerais_var
        # self.calc_notes_var = tk.StringVar() 
        self.anotacoes_gerais_var = tk.StringVar() # NOVO: Variável para a nova aba Anotações

        self.vol_data_var = tk.StringVar(value=date.today().strftime(DATA_FORMATO_CURTO)) 
        self.vol_volume_var = tk.StringVar()
        self.vol_notas_var = tk.StringVar()
        self.vol_total_var = tk.StringVar()
        self.vol_faltante_var = tk.StringVar()
        self.vol_media_diaria_var = tk.StringVar()
        
        # Live Flow Counter Variables
        self.vol_live_counter = tk.IntVar(value=0) # Armazena o valor numérico
        self.vol_live_counter_display_var = tk.StringVar(value="0") # Armazena o valor formatado para exibição
        
        # Metas Diárias (Input do usuário) - NOVAS VARS
        # RENOMEADO: meta_diaria_1 -> meta_pro_diaria
        self.vol_meta_pro_diaria_var = tk.StringVar(value="200") 
        # RENOMEADO: meta_diaria_2 -> meta_premium_diaria
        self.vol_meta_premium_diaria_var = tk.StringVar(value="225") 

        # REMOVIDO: Variável para Meta Mensal MANUAL/Prioritária (string para permitir entrada vazia)
        # self.vol_meta_mensal_input_var = tk.StringVar(value="")
        
        # Metas Mensais (Calculadas ou lidas do arquivo, mas valor de exibição)
        self.meta_mensal = 4500 # Será o valor da Meta PREMIUM Mensal Calculada
        self.vol_meta_mensal_display_var = tk.StringVar(value="4500") 
        self.vol_meta_feedback_var = tk.StringVar(value="") 
        
        self.meta_batida_mes = tk.StringVar(value="") 
        self.meta_batida_feedback = tk.StringVar(value="") 
        
        self.user_name_var = tk.StringVar()
        self.team_var = tk.StringVar()
        self.dob_var = tk.StringVar()
        self.daily_time_var = tk.StringVar(value="") 
        
        self._gui_ready = False
        self._agendas_initialized = False # Adicionado para controlar a inicialização da aba Agendas

    def configurar_estilos(self):
        """Configura os estilos do TTK, priorizando um visual flat e moderno."""
        fonte_principal = ("Segoe UI", 10)
        fonte_titulo = ("Segoe UI", 12, "bold")
        fonte_meta = ("Segoe UI", 11, "bold")
        
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        
        self.configure(bg=BACKGROUND_GRAY)
        self.style.configure(".", font=fonte_principal, background=BACKGROUND_GRAY)

        # Notebook (Abas)
        self.style.configure("TNotebook", background=BACKGROUND_GRAY, borderwidth=0)
        self.style.configure("TNotebook.Tab", font=fonte_titulo, padding=[15, 8], 
                        background=LIGHT_BLUE, foreground=PRIMARY_BLUE, borderwidth=0)
        # Efeito de seleção mais impactante
        self.style.map("TNotebook.Tab", 
                  background=[("selected", PRIMARY_BLUE), ("active", LIGHT_BLUE)],
                  foreground=[("selected", "white"), ("active", PRIMARY_BLUE)])

        # Botões Principais (Flat e com cores de destaque)
        self.style.configure("TButton", font=fonte_principal, padding=10, relief="flat", 
                        background=PRIMARY_BLUE, foreground="white", borderwidth=0)
        self.style.map("TButton", 
                  background=[("active", "#0055AA"), ("disabled", "gray")], 
                  relief=[("pressed", "flat"), ("!disabled", "flat")])
        
        # Estilo para os botões da toolbar (minimalista e compacto, com hover sutil)
        self.style.configure("Toolbar.TButton", font=("Segoe UI", 9), padding=4, relief="flat", 
                            background="#FFFFFF", foreground="#333333", borderwidth=0)
        self.style.map("Toolbar.TButton", 
                       background=[("active", "#F0F0F0"), ("pressed", LIGHT_BLUE)],
                       foreground=[("pressed", PRIMARY_BLUE)])
                       
        # Labelframe (Containers com fundo branco e borda sutil)
        self.style.configure("TLabelframe", padding=15, background="#FFFFFF", relief="flat", borderwidth=1, bordercolor="#DDDDDD")
        self.style.configure("TLabelframe.Label", font=fonte_titulo, foreground=PRIMARY_BLUE, background="#FFFFFF")
        
        # Treeview (Listas/Tabelas)
        self.style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF", foreground="#333333", 
                        rowheight=25, borderwidth=0)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"), background=LIGHT_BLUE, foreground=PRIMARY_BLUE, relief="flat")
        self.style.map("Treeview", background=[('selected', PRIMARY_BLUE)], foreground=[('selected', 'white')])
        
        # Tags de Agenda
        self.style.configure('daily_wday.Treeview', background='#FFF5E6', foreground='#A0522D') 
        self.style.configure('single.Treeview', background='#E6F5FF', foreground='#004494') 
        # NOVA TAG: para recorrência personalizada
        self.style.configure('custom_wday.Treeview', background='#F0EFFF', foreground='#6A0DAD') 

        # Labels específicos
        self.style.configure("Meta.TLabel", font=fonte_meta, foreground=PRIMARY_BLUE, background="#FFFFFF")
        self.style.configure("Faltante.TLabel", font=fonte_meta, foreground=DANGER_RED, background="#FFFFFF")
        self.style.configure("Media.TLabel", font=fonte_meta, foreground=SUCCESS_GREEN, background="#FFFFFF")
        self.style.configure("Feedback.TLabel", font=("Segoe UI", 13, "italic"), background="#FFFFFF", foreground=SUCCESS_GREEN)
        self.style.configure("Parabens.TLabel", font=("Segoe UI", 13, "bold"), background="#FFFFFF", foreground=PRIMARY_BLUE)
        self.style.configure("Motivacao.TLabel", font=("Segoe UI", 13, "bold"), background="#FFFFFF", foreground=DANGER_RED)
        
        # Estilo para o Contador de Fluxo
        self.style.configure("Counter.TLabel", font=("Segoe UI", 36, "bold"), foreground=PRIMARY_BLUE, background="#FFFFFF")
        
        # Estilo da Barra de Status (Mais flat e clean)
        self.style.configure("Status.TFrame", background="#FFFFFF", borderwidth=0, relief="flat")
        self.style.configure("Status.TLabel", background="#FFFFFF", foreground="#333333", font=("Segoe UI", 9))
        self.style.configure("Info.TLabel", background="#FFFFFF", foreground=PRIMARY_BLUE, font=("Segoe UI", 10, "bold"))
        self.style.configure("Header.TLabel", background=BACKGROUND_GRAY, foreground=PRIMARY_BLUE, font=("Segoe UI", 10, "bold"))

        # Estilo para o Painel da Daily
        self.style.configure("Daily.TLabelframe", background="#FFF5E6", relief="flat", borderwidth=1, bordercolor="#FFD700")
        self.style.configure("Daily.TLabelframe.Label", font=fonte_titulo, foreground="#A0522D", background="#FFF5E6")
        self.style.configure("DailyInfo.TLabel", background="#FFF5E6", foreground="#A0522D", font=("Segoe UI", 10, "bold"))

        # Novo Estilo para Entrys Customizadas (aparência flat com sublinhado)
        self.style.configure("Custom.TEntry", borderwidth=1, relief="flat", fieldbackground="#FFFFFF")
        self.style.map("Custom.TEntry", 
                       fieldbackground=[("focus", "#EFEFEF")],
                       bordercolor=[("focus", PRIMARY_BLUE)])


    def criar_menu_bar(self):
        """Cria a barra de menu no topo da aplicação."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuração", menu=config_menu)
        
        # ÚNICA OPÇÃO DE CONFIGURAÇÕES GERAIS
        config_menu.add_command(label="Configurações Gerais...", command=self.show_general_config_window)
        
        config_menu.add_separator()
        
        links_menu = tk.Menu(config_menu, tearoff=0)
        config_menu.add_cascade(label="Consulta (Links)", menu=links_menu)
        links_menu.add_command(label="Adicionar Link...", command=self.adicionar_link)
        links_menu.add_command(label="Remover Link...", command=self.remover_link)
        
        config_menu.add_separator()
        config_menu.add_command(label="Restaurar Padrões Originais...", command=self.confirmar_restauracao)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Arquivo", menu=file_menu)
        file_menu.add_command(label="Salvar Dados Agora", command=self.save_all_data)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.on_closing)


    def criar_widgets_principais(self):
        """Cria o Notebook (abas) e a Barra de Status."""
        
        # --- Frame do Cabeçalho ---
        # Removido o Status.TFrame para usar o fundo padrão do tk.Tk e parecer mais nativo.
        frame_top_info = ttk.Frame(self, style="TFrame", padding=(15, 0)) 
        frame_top_info.pack(side=tk.TOP, fill="x", anchor="n", padx=0, pady=(5, 0)) # Padding horizontal movido para o frame interno

        # Posicionando a Próxima Agenda e o Horário no canto superior direito
        ttk.Label(frame_top_info, textvariable=self.next_agenda_var, style="Header.TLabel").pack(side=tk.RIGHT, padx=(10, 0), pady=5)
        ttk.Label(frame_top_info, text="|", style="Status.TLabel", foreground="#999999", background=BACKGROUND_GRAY).pack(side=tk.RIGHT, padx=0, pady=5) 
        ttk.Label(frame_top_info, textvariable=self.time_var, style="Header.TLabel").pack(side=tk.RIGHT, padx=(0, 10), pady=5)
        ttk.Label(frame_top_info, text="").pack(side=tk.LEFT, fill=tk.X, expand=True) # Espaçador
        
        # >>> LINHA REMOVIDA: ttk.Separator(self, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill="x", padx=15, pady=0)


        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=(5, 10), padx=15, fill="both", expand=True)

        self.criar_aba_devolutivas()
        self.criar_aba_consulta()
        self.criar_aba_calculadora()
        self.criar_aba_volumetria()
        self.criar_aba_anotacoes() # NOVO: Aba Anotações adicionada após Volumetria
        
        # A aba Agendas é tratada aqui para controle de inicialização
        self.aba_agendas_frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.aba_agendas_frame, text="Agendas")
        
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # --- Barra de Status (Rodapé, visual clean) ---
        status_frame = ttk.Frame(self, relief=tk.FLAT, style="Status.TFrame")
        status_frame.pack(side=tk.BOTTOM, fill="x", anchor="s")
        
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w", padding=5, style="Status.TLabel", background="#FFFFFF")
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True) 
        
        self._gui_ready = True
        
        self.atualizar_lista_links()
        self.update_calc_history_display()
        self.atualizar_treeview_volumetria()
        self.atualizar_lista_agendas()
        
    def _on_tab_change(self, event):
        """Verifica se a aba Agendas foi selecionada e força a configuração da Daily."""
        selected_tab_index = self.notebook.index(self.notebook.select())
        tab_text = self.notebook.tab(selected_tab_index, "text")

        if tab_text == "Anotações":
            # Força o ScrolledText a recarregar o conteúdo e ter foco (se necessário)
            self._update_anotacoes_content(event=None, save_to_var=False) 
            
        elif tab_text == "Agendas":
             if not self._agendas_initialized:
                 self.criar_aba_agendas()
                 self._agendas_initialized = True
                 
             # Se o nome está preenchido, mas a hora da daily não, força o input (apenas se for a 1ª vez que abre Agendas)
             if not self.daily_time_var.get().strip() and self.user_name_var.get().strip():
                 self.after(0, self._force_daily_time_input)

        
    # --- Funções Auxiliares de I/O ---
    def carregar_json(self, nome_arquivo, funcao_padrao):
        """Função genérica para carregar um arquivo JSON."""
        if os.path.exists(nome_arquivo):
            try:
                with open(nome_arquivo, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erro ao carregar {nome_arquivo}: {e}")
                return funcao_padrao()
        else:
            return funcao_padrao()

    def salvar_json(self, nome_arquivo, data):
        """Função genérica para salvar um arquivo JSON."""
        try:
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            if hasattr(self, 'status_var'):
                 self.atualizar_status(f"Erro ao salvar {nome_arquivo}: {e}")
            print(f"Erro ao salvar {nome_arquivo}: {e}")
            return False
    
    def _save_config_data(self, config_data):
        self.salvar_json(ARQUIVO_CONFIG, config_data)
        
    def carregar_config_padrao(self):
        # ATUALIZADO: Metas padrão agora são diárias (200 e 225) e as mensais são o resultado do cálculo
        working_days = self.get_total_working_days_in_month()
        meta_pro_diaria = 200
        meta_premium_diaria = 225
        
        return {
            "nome": "", "time": "", "data_nascimento": "",
            # RENOMEADO: meta_diaria_1 -> meta_pro_diaria
            "meta_pro_diaria": meta_pro_diaria, 
            # RENOMEADO: meta_diaria_2 -> meta_premium_diaria
            "meta_premium_diaria": meta_premium_diaria,
            # RENOMEADO: meta_mensal_1 -> meta_pro_mensal (calculado)
            "meta_pro_mensal": meta_pro_diaria * working_days, 
            # RENOMEADO: meta_mensal_2 -> meta_premium_mensal (calculado)
            "meta_premium_mensal": meta_premium_diaria * working_days,
            # REMOVIDO: "meta_mensal_input": ""
            "meta_batida_mes": "", "meta_batida_feedback": "",
            "daily_time": ""
        }
        
    def carregar_anotacoes_padrao(self):
        """Retorna o conteúdo padrão (vazio) para anotações gerais."""
        return {"anotacoes": "Use este espaço para anotações rápidas e temporárias."}

    def carregar_devolutivas_config_padrao(self):
        """Nova função: Retorna o objeto de configuração padrão para devolutivas."""
        return {"active_profile": "Personalizada"}
        
    # --- Funções de Data e Máscara ---
    
    def _validate_time_format(self, time_string):
        """Valida o formato HH:MM."""
        if not re.match(r'^\d{2}:\d{2}$', time_string):
            return False
        try:
            # Verifica se a hora e minuto são válidos (ex: não permite 25:99)
            hour, minute = map(int, time_string.split(':'))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return True
            return False
        except ValueError:
            return False
            
    def _apply_time_masking(self, event):
        """Aplica a máscara de hora em tempo real (HH:MM)."""
        widget = event.widget
        # Se for um evento de FocusOut, não executa o masking, apenas valida
        if event.type == '9': # FocusOut
            return 
            
        current_text = widget.get().replace(':', '')
        max_len = 4
        
        if len(current_text) > max_len:
            current_text = current_text[:max_len]
        
        new_text = ""
        for i, char in enumerate(current_text):
            if not char.isdigit(): continue
            new_text += char
            
            if len(new_text) == 2 and i < max_len - 1:
                new_text += ':'

        if len(new_text) == 3 and new_text[-1] == ':': new_text = new_text[:-1]
        if len(new_text) > max_len + 1: new_text = new_text[:max_len + 1]


        widget.delete(0, tk.END)
        widget.insert(0, new_text)
        
        widget.icursor(len(new_text))
             
    def _validate_date_format(self, date_string, is_long_format=False):
        """Valida o formato de data DD/MM."""
        if is_long_format:
            # Assume que se é formato longo, a data está correta (vem de um objeto datetime)
            return True
        
        if not re.match(r'^\d{2}/\d{2}$', date_string):
            return False
        try:
            self._parse_full_date(date_string, DATA_FORMATO_CURTO)
            return True
        except ValueError:
            return False

    def _parse_full_date(self, date_short_str, short_format):
        """Converte DD/MM para objeto datetime usando o ano atual e trata a validação do dia/mês."""
        current_year = str(date.today().year)
        date_with_year = f"{date_short_str}/{current_year}"
        
        try:
            # Tenta analisar DD/MM/YYYY. O Python valida se 31/02 é um erro.
            return datetime.strptime(date_with_year, f"%d/%m/%Y")
        except ValueError:
             raise ValueError(f"Data inválida (Dia/Mês fora do range ou formato incorreto).")

    def _apply_date_masking(self, event, format_type='long'):
        """Aplica a máscara de data DD/MM."""
        widget = event.widget
        
        # Se for um evento de FocusOut, não executa o masking
        if event.type == '9': # FocusOut
            return 
            
        current_text = widget.get().replace('/', '')
        
        max_len = 4
        
        if len(current_text) > max_len:
            current_text = current_text[:max_len]
        
        new_text = ""
        for i, char in enumerate(current_text):
            if not char.isdigit(): continue
            new_text += char
            
            if len(new_text) == 2 and i < max_len - 1:
                new_text += '/'

        # CORRIGIDO: Garante que apenas o último caractere (se for '/') seja removido
        if len(new_text) > 2 and new_text[-1] == '/': new_text = new_text[:-1]

        widget.delete(0, tk.END)
        widget.insert(0, new_text)
        
        widget.icursor(len(new_text))


    # --- Funções de Inicialização de Dados ---
    def carregar_agendas_zero(self): return []
    def carregar_volumetria_zero(self): return {"registros": []}
    def carregar_calculadora_vazia(self): return {"history": []} # Notas removidas
    def carregar_links_padrao(self):
        return [
            {"nome": "Senior", "url": "https://platform.senior.com.br/senior-x/#/"},
            {"nome": "Receita (Consulta CNPJ)", "url": "https://solucoes.receita.fazenda.gov.br/servicos/cnpjreva/cnpjreva_solicitacao.asp"},
            {"nome": "Simples Nacional", "url": "https://www8.receita.fazenda.gov.br/simplesnacional/"},
            {"nome": "Validar Assinatura (ITI)", "url": "https://validar.iti.gov.br/"}
        ]
        
    def carregar_devolutivas_padrao(self):
        """
        [MODIFICADO] Cria os arquivos JSON individuais dos perfis padrão, garantindo que
        o perfil "Padrão" não seja criado por padrão.
        """
        
        # Macros Padrão com exemplos (apenas para o perfil Personalizada)
        # CORRIGIDO: O perfil Personalizada deve vir vazio!
        textos_personalizada = [""] * 9
        
        # REMOVIDO "Padrão" daqui.
        profile_names = [
            "Personalizada", "Pessoa", "Endereço", "Bem Novo", 
            "Fonte de Renda PF", "Fonte de Renda PJ", "Relacionamento"
        ]
        
        # Cria e salva o arquivo de cada perfil se ele ainda não existir
        for name in profile_names:
            filepath = get_profile_filepath(name)
            if not os.path.exists(filepath):
                # O perfil "Personalizada" receberá as macros iniciais vazias
                macros = textos_personalizada if name == "Personalizada" else [""] * 9
                
                # Para fins de exemplo, vamos manter o texto de exemplo para os outros perfis
                # para que eles não venham todos vazios.
                if name != "Personalizada":
                    macros = [
                        "Texto de exemplo para perfil: " + name + " (1)",
                        "Texto de exemplo para perfil: " + name + " (2)",
                        "Texto de exemplo para perfil: " + name + " (3)",
                        "", "", "", "", "", ""
                    ]
                
                self.salvar_json(filepath, {"macros": macros})
            
        return profile_names # Retorna a lista sem "Padrão"


    def carregar_volumetria_padrao(self):
        """Retorna os dados padrão de volumetria."""
        data_hoje_str = date.today().strftime(DATA_FORMATO_LONGO_PERSIST) 
        
        dados_padrao = [
            {"data": date.today().replace(day=1).strftime(DATA_FORMATO_LONGO_PERSIST), "volume": "183", "notas": "Exemplo de registro de início de mês."}, 
            {"data": data_hoje_str, "volume": "227", "notas": "Registro de hoje."} 
        ]
            
        return {"registros": dados_padrao}

    def carregar_agendas_padrao(self):
        """Cria agendas de exemplo (apenas as de Única Data)."""
        today = date.today().strftime(DATA_FORMATO_LONGO_PERSIST)
        
        return [
            {"data": today, "hora": "10:30", "descricao": "Reunião de Alinhamento Semanal", "link": "", "repeticao": "single" },
            {"data": today, "hora": "15:00", "descricao": "Sessão de Treinamento", "link": "", "repeticao": "single" }
        ]

        
    def carregar_dados_iniciais(self):
        """Carrega todos os dados, garantindo consistência na 1ª execução."""
        is_first_run = not os.path.exists(ARQUIVO_FLAG_INIT)
        
        # 1. Garante que os arquivos de perfis padrão existam
        self.devolutivas_profiles = self.carregar_devolutivas_padrao()
        
        # 2. Carrega/cria a configuração de qual perfil está ativo
        data_dev_config = self.carregar_json(ARQUIVO_DEVOLUTIVAS_CONFIG, self.carregar_devolutivas_config_padrao)
        active_name = data_dev_config.get("active_profile", "Personalizada")
        
        # Garante que o perfil ativo existe, senão volta para o Personalizada (agora o único padrão)
        if active_name not in self.devolutivas_profiles or active_name == "Padrão":
            active_name = "Personalizada"
            
        self.devolutivas_active_profile_name.set(active_name)
        
        if is_first_run:
            print("PRIMEIRA EXECUÇÃO DETECTADA: Criando arquivos padrão (DB) e o flag de inicialização.")
            
            # Salva a config do perfil ativo
            self.salvar_json(ARQUIVO_DEVOLUTIVAS_CONFIG, {"active_profile": self.devolutivas_active_profile_name.get()})
            
            self.agendas_data = self.carregar_agendas_zero()
            self.salvar_json(ARQUIVO_AGENDAS, self.agendas_data)
            
            data_vol = self.carregar_volumetria_zero()
            self.salvar_json(ARQUIVO_VOLUMETRIA, data_vol)
            
            calc_data = self.carregar_calculadora_vazia()
            self.salvar_json(ARQUIVO_CALCULADORA, calc_data)
            
            config_data = self.carregar_config_padrao()
            self._save_config_data(config_data)

            anotacoes_data = self.carregar_anotacoes_padrao()
            self.salvar_json(ARQUIVO_ANOTACOES, anotacoes_data)
            
            try:
                with open(ARQUIVO_FLAG_INIT, "w", encoding="utf-8") as f:
                    f.write(datetime.now().isoformat())
            except Exception as e:
                print(f"Erro ao criar ARQUIVO_FLAG_INIT: {e}")
            
            self.calc_history = calc_data.get("history", [])
            self.anotacoes_gerais_var.set(anotacoes_data.get("anotacoes", ""))
            
        else:
            print("Inicialização normal: Carregando dados existentes.")
            
            self.agendas_data = self.carregar_json(ARQUIVO_AGENDAS, self.carregar_agendas_zero)
            data_vol = self.carregar_json(ARQUIVO_VOLUMETRIA, self.carregar_volumetria_zero)
            calc_data = self.carregar_json(ARQUIVO_CALCULADORA, self.carregar_calculadora_vazia)
            anotacoes_data = self.carregar_json(ARQUIVO_ANOTACOES, self.carregar_anotacoes_padrao)
            
            self.calc_history = calc_data.get("history", [])
            self.anotacoes_gerais_var.set(anotacoes_data.get("anotacoes", ""))

        # 3. Carrega o restante
        self.links_data = self.carregar_json(ARQUIVO_LINKS, self.carregar_links_padrao)
        self.carregar_config() 
        self.load_active_profile_macros()
        
        self.volumetria_data = data_vol.get('registros', [])


    # --- Funções de Perfil/Configuração ---

    def carregar_config(self):
        """
        Carrega as configurações do usuário.
        [MODIFICADO] Carrega Meta PRO e Meta PREMIUM, e define o self.meta_mensal como PREMIUM calculado.
        """
        config_data = self.carregar_json(ARQUIVO_CONFIG, self.carregar_config_padrao)
        
        # Carrega dados do perfil
        self.user_name_var.set(config_data.get("nome", ""))
        self.team_var.set(config_data.get("time", ""))
        self.daily_time_var.set(config_data.get("daily_time", ""))

        # Carrega as metas DIÁRIAS salvas (Input do usuário) - Usando novos nomes de chaves
        meta_pro_diaria = config_data.get("meta_pro_diaria", 200)
        meta_premium_diaria = config_data.get("meta_premium_diaria", 225)
        
        self.vol_meta_pro_diaria_var.set(str(meta_pro_diaria))
        self.vol_meta_premium_diaria_var.set(str(meta_premium_diaria))

        # 1. Calcula as metas MENSAIS automáticas
        working_days = self.get_total_working_days_in_month()
        meta_premium_mensal_calc = meta_premium_diaria * working_days
        
        # 2. Define o valor ATIVO (Meta PREMIUM Mensal Calculada)
        self.meta_mensal = meta_premium_mensal_calc
        self.vol_meta_mensal_display_var.set(str(self.meta_mensal))
        
        self.meta_batida_mes.set(config_data.get("meta_batida_mes", ""))
        self.meta_batida_feedback.set(config_data.get("meta_batida_feedback", ""))

        return config_data

    def salvar_config(self):
        """
        Salva as configurações do usuário com validação.
        [MODIFICADO] Salva as metas diárias PRO e PREMIUM e seus cálculos mensais.
        """
        daily_time = self.daily_time_var.get().strip()
        
        if daily_time and not self._validate_time_format(daily_time):
             # Não exibe mensagem de erro se a GUI não estiver pronta
             if self._gui_ready:
                 messagebox.showerror("Erro de Validação", "Ops! O formato da Hora da Daily precisa ser HH:MM (ex: 09:30). Vamos ajustar isso?")
             return False

        try:
            # Lendo as metas DIÁRIAS (Input do usuário)
            meta_pro_str = self.vol_meta_pro_diaria_var.get().strip()
            meta_premium_str = self.vol_meta_premium_diaria_var.get().strip()
            
            meta_pro_diaria = int(meta_pro_str) if meta_pro_str.isdigit() else 200
            meta_premium_diaria = int(meta_premium_str) if meta_premium_str.isdigit() else 225

            if meta_pro_diaria < 0 or meta_premium_diaria < 0: raise ValueError("As Metas diárias devem ser números positivos. Queremos ir pra frente!")

            # Verifica se a Premium é maior ou igual à Pro
            if meta_premium_diaria < meta_pro_diaria:
                 raise ValueError("A Meta PREMIUM deve ser maior ou igual à Meta PRO. Lembre-se, o PREMIUM é o seu alvo máximo!")
            
            # --- FIM VALIDAÇÃO ---
            
        except ValueError as ve:
            if self._gui_ready:
                 messagebox.showerror("Erro de Validação", f"Erro nas suas metas diárias. Detalhe: {ve}")
            return False
        
        # 1. CALCULA as metas MENSAIS AUTOMÁTICAS com base nos dias úteis do mês atual
        working_days = self.get_total_working_days_in_month()
        meta_pro_mensal_calc = meta_pro_diaria * working_days
        meta_premium_mensal_calc = meta_premium_diaria * working_days
        
        # 2. DEFINE O VALOR ATIVO (Meta PREMIUM Mensal Calculada)
        self.meta_mensal = meta_premium_mensal_calc
        self.vol_meta_mensal_display_var.set(str(self.meta_mensal))
        
        user_name_to_save = self.user_name_var.get().strip()
        
        config_data = {
            "nome": user_name_to_save, 
            "time": self.team_var.get(),
            "data_nascimento": "",
            # Salva o valor DIÁRIO PRO
            "meta_pro_diaria": meta_pro_diaria, 
            # Salva o valor DIÁRIO PREMIUM
            "meta_premium_diaria": meta_premium_diaria,
            # Salva o valor MENSAL CALCULADO PRO
            "meta_pro_mensal": meta_pro_mensal_calc, 
            # Salva o valor MENSAL CALCULADO PREMIUM
            "meta_premium_mensal": meta_premium_mensal_calc,
            "meta_batida_mes": self.meta_batida_mes.get(), "meta_batida_feedback": self.meta_batida_feedback.get(),
            "daily_time": daily_time
        }
        self._save_config_data(config_data) 
        
        if self._gui_ready:
            self.after(0, self.atualizar_treeview_volumetria)
            self.after(0, self.atualizar_lista_agendas)
            
        return True
    
    def salvar_perfil(self):
        first_name = self._get_first_name()
        if self.salvar_config():
            self.atualizar_status(f"Configurações de Perfil salvas com sucesso! Excelente, {first_name}!")
        else:
            self.atualizar_status("Ops! Houve um erro ao salvar suas Configurações de Perfil. Tente novamente.")
            
    def salvar_metas(self):
        first_name = self._get_first_name()
        if self.salvar_config():
            self.atualizar_status(f"Metas de Volumetria atualizadas! Vamos em frente, {first_name}!")
        else:
            self.atualizar_status("Houve um erro ao salvar suas Metas de Volumetria. Vamos corrigir isso?")


    def _force_daily_time_input(self):
        """Abre uma janela modal para forçar o usuário a definir a hora da daily."""
        
        if self.daily_time_var.get().strip() or (hasattr(self, 'daily_force_window') and self.daily_force_window and self.daily_force_window.winfo_exists()):
            return
            
        if not self.user_name_var.get().strip():
            return

        self.daily_force_window = tk.Toplevel(self)
        self.daily_force_window.title("Configuração da Daily")
        self.daily_force_window.transient(self)
        self.daily_force_window.grab_set() 
        self.daily_force_window.resizable(False, False)
        
        first_name = self._get_first_name()
        
        frame = ttk.Frame(self.daily_force_window, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, 
                  text=f"Olá {first_name}! Para não perder o alinhamento, por favor, defina a hora da sua Daily (Seg-Sex).", 
                  font=("Segoe UI", 11), foreground=PRIMARY_BLUE, wraplength=350).pack(pady=(0, 15), anchor="w")

        ttk.Label(frame, text=f"Hora da Daily ({HORA_DISPLAY}):", font=("Segoe UI", 10, "bold")).pack(pady=(5, 5), anchor="w")
        
        v_temp_daily_time = tk.StringVar(value="")
        entry_daily_time = ttk.Entry(frame, textvariable=v_temp_daily_time, width=10, style="Custom.TEntry")
        entry_daily_time.pack(pady=5, ipady=4, anchor="w")
        entry_daily_time.focus()
        entry_daily_time.bind("<KeyRelease>", self._apply_time_masking)
        
        def save_and_close():
            daily_time_input = v_temp_daily_time.get().strip()
            
            if not self._validate_time_format(daily_time_input):
                messagebox.showerror("Erro de Validação", "Ops! O formato da Hora precisa ser HH:MM (ex: 09:30).")
                entry_daily_time.focus()
                return
            
            self.daily_time_var.set(daily_time_input)
            
            if self.salvar_config():
                self.daily_force_window.destroy()
            else:
                 self.daily_time_var.set("") 


        btn_salvar = ttk.Button(frame, text="Salvar Hora da Daily", command=save_and_close, style="TButton")
        btn_salvar.pack(fill="x", pady=15, ipady=8)
        
        self.daily_force_window.protocol("WM_DELETE_WINDOW", lambda: messagebox.showerror("Atenção", "Para garantir que você use os lembretes, precisamos da hora da Daily. Por favor, insira para continuar."))
        
        self.daily_force_window.update_idletasks()
        w = self.daily_force_window.winfo_reqwidth()
        h = self.daily_force_window.winfo_reqheight()
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        self.daily_force_window.geometry(f'+{x}+{y}')
        
        self.wait_window(self.daily_force_window)


    def show_initial_setup(self):
        """Abre a janela modal de configuração inicial."""
        setup_window = tk.Toplevel(self)
        setup_window.title("Configuração Inicial do Perfil")
        setup_window.transient(self)
        setup_window.grab_set() 
        setup_window.resizable(False, False)
        
        setup_window.protocol("WM_DELETE_WINDOW", lambda: messagebox.showerror("Atenção", "O Primeiro Nome é obrigatório! Queremos te chamar pelo nome e celebrar suas conquistas. Por favor, preencha para continuar."))
        
        tab_config = ttk.Frame(setup_window, padding=20)
        # CORRIGIDO: O frame agora preenche verticalmente
        tab_config.pack(fill="both", expand=True)

        ttk.Label(tab_config, 
                  text="Bem-vindo(a)! Para começar com o pé direito, preencha seu perfil. Assim, podemos personalizar suas metas e lembretes.", 
                  font=("Segoe UI", 11), foreground=PRIMARY_BLUE, wraplength=400).pack(pady=(0, 20), anchor="w")

        frame_perfil = ttk.LabelFrame(tab_config, text="Perfil do Usuário", style="TLabelframe")
        frame_perfil.pack(fill="x", pady=10)
        frame_perfil.columnconfigure(1, weight=1)

        ttk.Label(frame_perfil, text="Seu Primeiro Nome (Obrigatório):").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        entry_name = ttk.Entry(frame_perfil, textvariable=self.user_name_var, style="Custom.TEntry")
        entry_name.grid(row=0, column=1, sticky="ew", padx=10, pady=5, ipady=4)
        entry_name.focus() 
        
        ttk.Label(frame_perfil, text="Seu Time:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        ttk.Entry(frame_perfil, textvariable=self.team_var, style="Custom.TEntry").grid(row=1, column=1, sticky="ew", padx=10, pady=5, ipady=4)

        ttk.Label(frame_perfil, text=f"Hora da Daily ({HORA_DISPLAY}):", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        entry_daily_time = ttk.Entry(frame_perfil, textvariable=self.daily_time_var, style="Custom.TEntry", width=10)
        entry_daily_time.grid(row=2, column=1, sticky="w", padx=10, pady=5, ipady=4)
        entry_daily_time.bind("<KeyRelease>", self._apply_time_masking)
        
        # Salvamento automático do perfil ao perder o foco
        def save_on_focus_out(event):
            self.salvar_config()
            
        # O bind nos Entrys já é suficiente, o bloco try/except abaixo não é necessário
        # e estava causando confusão de tipo de objeto.

        
        def save_and_close():
            if not self.user_name_var.get().strip():
                messagebox.showerror("Erro de Validação", "O campo 'Primeiro Nome' é obrigatório. Queremos te dar parabéns!")
                return
            
            first_name = self._get_first_name()
            
            if self.salvar_config(): 
                setup_window.destroy()
                messagebox.showinfo("Sucesso", f"Configuração inicial salva! Seu SmartBPO está pronto para uso. Vamos brilhar, {first_name}!")
                
                self.after(0, self.criar_widgets_principais)
                self.after(100, self._iniciar_tarefas_assincronas)
                

        btn_salvar = ttk.Button(tab_config, text="Salvar e Continuar", command=save_and_close, style="TButton")
        # CORREÇÃO: Removido o fill="x" do pack do botão e ele será empacotado no FINAL do tab_config (que tem expand=True)
        # Agora o botão aparece, mas vamos garantir o fill="x" para estética.
        btn_salvar.pack(fill="x", pady=20, ipady=10) # <-- OTIMIZADO

        setup_window.update_idletasks()
        # Removida a linha de geometria 'fixa' que estava causando o problema
        # O Toplevel agora redimensiona automaticamente para caber o conteúdo
        
        # Centralizando a janela de setup
        w = setup_window.winfo_reqwidth()
        h = setup_window.winfo_reqheight()
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        setup_window.geometry(f'{w}x{h}+{x}+{y}') 
        
        self.wait_window(setup_window)

    def show_general_config_window(self):
        """NEW: Cria e exibe a janela Toplevel principal de Configurações Gerais com abas."""
        if self.config_window and self.config_window.winfo_exists():
            self.config_window.lift()
            return
            
        self.config_window = tk.Toplevel(self)
        self.config_window.title("Configurações Gerais do SmartBPO")
        self.config_window.transient(self)
        self.config_window.grab_set() 
        self.config_window.resizable(False, False)
        
        main_frame = ttk.Frame(self.config_window, padding=15)
        main_frame.pack(fill="both", expand=True)
        
        notebook_config = ttk.Notebook(main_frame)
        notebook_config.pack(fill="both", expand=True, pady=(0, 10))
        
        # --- Aba 1: Geral (Perfil + Daily) ---
        tab_geral = ttk.Frame(notebook_config, padding=10)
        notebook_config.add(tab_geral, text="Geral (Perfil e Daily)")
        self._create_config_tab_geral(tab_geral)
        
        # --- Aba 2: Metas ---
        tab_metas = ttk.Frame(notebook_config, padding=10)
        notebook_config.add(tab_metas, text="Metas de Volumetria")
        self._create_config_tab_metas(tab_metas)
        
        # --- Aba 3: Perfis de Devolutivas ---
        tab_perfis = ttk.Frame(notebook_config, padding=10)
        notebook_config.add(tab_perfis, text="Perfis de Devolutivas")
        self._create_config_tab_perfis(tab_perfis)

        # --- Aba 4: Avançado (Restauração) ---
        tab_avancado = ttk.Frame(notebook_config, padding=10)
        notebook_config.add(tab_avancado, text="Avançado")
        self._create_config_tab_avancado(tab_avancado)

        # Botão Salvar (Global)
        btn_salvar_global = ttk.Button(main_frame, text="Salvar e Atualizar Configurações", command=self.salvar_perfil_e_metas_config)
        btn_salvar_global.pack(fill="x", padx=5, pady=(10, 0), ipady=8)


        self.config_window.update_idletasks()
        w = self.config_window.winfo_reqwidth()
        h = self.config_window.winfo_reqheight()
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        self.config_window.geometry(f'+{x}+{y}')
        
        self.config_window.protocol("WM_DELETE_WINDOW", self.config_window.destroy)

    def _create_config_tab_geral(self, parent):
        """Cria o conteúdo da aba Geral (Perfil e Daily)."""
        
        frame_perfil = ttk.LabelFrame(parent, text="Dados do Usuário", style="TLabelframe")
        frame_perfil.pack(fill="x", pady=10, padx=5)
        frame_perfil.columnconfigure(1, weight=1)

        ttk.Label(frame_perfil, text="Seu Primeiro Nome:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        ttk.Entry(frame_perfil, textvariable=self.user_name_var, style="Custom.TEntry").grid(row=0, column=1, sticky="ew", padx=10, pady=5, ipady=4)
        
        ttk.Label(frame_perfil, text="Seu Time:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        ttk.Entry(frame_perfil, textvariable=self.team_var, style="Custom.TEntry").grid(row=1, column=1, sticky="ew", padx=10, pady=5, ipady=4)

        frame_daily = ttk.LabelFrame(parent, text="Configuração de Agendamento Diário", style="TLabelframe")
        frame_daily.pack(fill="x", pady=10, padx=5)
        frame_daily.columnconfigure(1, weight=1)
        
        ttk.Label(frame_daily, text=f"Hora da Daily ({HORA_DISPLAY}):", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        entry_daily_time = ttk.Entry(frame_daily, textvariable=self.daily_time_var, style="Custom.TEntry", width=10)
        entry_daily_time.grid(row=0, column=1, sticky="w", padx=10, pady=5, ipady=4)
        entry_daily_time.bind("<KeyRelease>", self._apply_time_masking)
        
        ttk.Label(parent, text="Tudo é salvo quando você clica em 'Salvar e Atualizar Configurações'.", font=("Segoe UI", 9, "italic"), foreground="gray").pack(pady=(10, 5), anchor="w")
        
    def _create_config_tab_metas(self, parent):
        """
        Cria o conteúdo da aba Metas de Volumetria, usando Meta PRO e Meta PREMIUM.
        [MODIFICADO] Simplifica a interface, remove input manual, renomeia rótulos.
        """
        
        # Recalcula os dias úteis para o display
        working_days = self.get_total_working_days_in_month()
        
        frame_metas = ttk.LabelFrame(parent, text=f"Metas Diárias e Cálculo Mensal (Dias úteis no mês: {working_days})", style="TLabelframe")
        frame_metas.pack(fill="x", pady=10, padx=5)
        
        # Grid para 4 colunas: Rótulo Input | Input | Rótulo Cálculo | Valor Cálculo
        frame_metas.columnconfigure(1, weight=1)
        
        # --- Meta Diária PRO ---
        ttk.Label(frame_metas, text="Meta Diária PRO (Qualidade):").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        entry_pro_diaria = ttk.Entry(frame_metas, textvariable=self.vol_meta_pro_diaria_var, style="Custom.TEntry", width=15)
        entry_pro_diaria.grid(row=0, column=1, sticky="w", padx=10, pady=5, ipady=4)
        
        # --- Meta Mensal PRO (Display Calculado) ---
        ttk.Label(frame_metas, text=f"Mensal Calculada PRO:", font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=10, pady=5)
        
        # Cálculo do valor PRO para exibição imediata
        meta_mensal_pro_calc = self.get_total_working_days_in_month() * (int(self.vol_meta_pro_diaria_var.get()) if self.vol_meta_pro_diaria_var.get().isdigit() else 200)
        
        ttk.Label(frame_metas, text=str(meta_mensal_pro_calc), foreground="#666666", font=("Segoe UI", 10)).grid(row=0, column=3, sticky="w", padx=10, pady=5)

        # --- Meta Diária PREMIUM ---
        ttk.Label(frame_metas, text="Meta Diária PREMIUM (Premiação):").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        entry_premium_diaria = ttk.Entry(frame_metas, textvariable=self.vol_meta_premium_diaria_var, style="Custom.TEntry", width=15)
        entry_premium_diaria.grid(row=1, column=1, sticky="w", padx=10, pady=5, ipady=4)

        # --- Meta Mensal PREMIUM (Display Calculado - É a meta principal) ---
        ttk.Label(frame_metas, text=f"Mensal Calculada PREMIUM:", font=("Segoe UI", 10, "bold")).grid(row=1, column=2, sticky="w", padx=10, pady=5)
        
        # Cálculo do valor PREMIUM para exibição imediata
        meta_mensal_premium_calc = self.get_total_working_days_in_month() * (int(self.vol_meta_premium_diaria_var.get()) if self.vol_meta_premium_diaria_var.get().isdigit() else 225)
        
        # Usa a StringVar de display principal que será atualizada com o valor da Meta PREMIUM
        ttk.Label(frame_metas, textvariable=self.vol_meta_mensal_display_var, foreground=PRIMARY_BLUE, font=("Segoe UI", 10, "bold")).grid(row=1, column=3, sticky="w", padx=10, pady=5)
        # Força a atualização do display para o valor calculado
        self.vol_meta_mensal_display_var.set(str(meta_mensal_premium_calc)) 
        
        # REMOVIDO o divisor e o campo de input manual (Meta Mensal Manual)

        ttk.Label(parent, text="A Meta PREMIUM é o nosso alvo de excelência, o caminho para a premiação!", font=("Segoe UI", 9, "italic"), foreground=DANGER_RED).pack(pady=(10, 5), anchor="w")

    def _create_config_tab_perfis(self, parent):
        """Cria o conteúdo da aba Gerenciamento de Perfis de Devolutivas."""
        
        frame_perfis = ttk.LabelFrame(parent, text="Ações de Perfil", style="TLabelframe")
        frame_perfis.pack(fill="x", pady=10, padx=5)
        
        ttk.Label(frame_perfis, text="Perfil Ativo (para remoção):", font=("Segoe UI", 10)).pack(pady=(5, 5), padx=10, anchor="w")
        
        # Exibe o perfil ativo atual para referência
        ttk.Label(frame_perfis, textvariable=self.devolutivas_active_profile_name, font=("Segoe UI", 12, "bold"), foreground=DANGER_RED).pack(pady=(0, 15), padx=10, anchor="w")
        
        btn_add = ttk.Button(frame_perfis, text="➕ Adicionar Novo Perfil", command=self.add_new_profile)
        btn_add.pack(fill="x", pady=(5, 5), padx=10, ipady=8)
        
        btn_remove = ttk.Button(frame_perfis, text="❌ Remover Perfil ATIVO (Irreversível)", command=self.remove_current_profile, style="Reset.TButton")
        btn_remove.pack(fill="x", pady=(5, 10), padx=10, ipady=8)
        
        ttk.Label(parent, text="A remoção é imediata e irreversível. Use com cuidado!", font=("Segoe UI", 9, "italic"), foreground="gray").pack(pady=(10, 5), anchor="w")


    def _create_config_tab_avancado(self, parent):
        """Cria o conteúdo da aba Avançado (Restauração)."""
        
        frame_avancado = ttk.LabelFrame(parent, text="Restauração de Dados", style="TLabelframe")
        frame_avancado.pack(fill="x", pady=10, padx=5)
        
        ttk.Label(frame_avancado, text="ATENÇÃO: Você vai apagar TODOS os seus registros (metas, agendas, históricos). Use esta opção apenas se for começar do zero.", font=("Segoe UI", 10, "bold"), foreground=DANGER_RED, wraplength=400).pack(pady=10, padx=10, anchor="w")

        btn_restaurar = ttk.Button(frame_avancado, text="RESTAURAR TODOS OS PADRÕES ORIGINAIS", command=self.confirmar_restauracao, style="Reset.TButton")
        btn_restaurar.pack(fill="x", padx=10, pady=15, ipady=8)
        
    def salvar_perfil_e_metas_config(self):
        """Salva as configurações de Perfil e Metas simultaneamente e fecha a janela."""
        if self.salvar_config(): 
            self.config_window.destroy()
            first_name = self._get_first_name()
            self.atualizar_status(f"Configurações gerais salvas! Mantenha o foco, {first_name}!")
        else:
             self.atualizar_status("Ops! Encontramos um erro ao salvar as configurações. Por favor, verifique os campos.")

    # --- Funções de Perfil de Devolutivas (NOVO) ---

    def _get_all_profile_names(self):
        """
        [MODIFICADO] Retorna uma lista de nomes de perfis, excluindo "Padrão", 
        e colocando "Personalizada" primeiro.
        """
        all_files = [
            file.stem.split('macros_')[-1].replace('_', ' ')
            for file in DATA_DIR.glob('macros_*.json')
        ]
        
        if not all_files:
            return []

        # Remove 'Padrão' da lista, se estiver presente (importante para usuários que tinham o perfil)
        regular_profiles = [name for name in all_files if name not in ["Padrão", "Personalizada"]]
        
        # Ordena os perfis restantes
        sorted_regular = sorted(regular_profiles)
        
        final_profiles = []
        # Adiciona Personalizada (se existir) no início
        if "Personalizada" in all_files:
            final_profiles.append("Personalizada")
            
        # Adiciona os perfis ordenados
        final_profiles.extend(sorted_regular)
        
        return final_profiles


    def get_current_profile_macros(self):
        """Retorna a lista de macros do perfil ativo lendo do arquivo."""
        active_name = self.devolutivas_active_profile_name.get()
        filepath = get_profile_filepath(active_name)
        
        data = self.carregar_json(filepath, lambda: {"macros": [""] * 9})
        macros = data.get("macros", [""] * 9)
        if len(macros) != 9: macros = [""] * 9 # Garante 9 macros
        return macros

    def load_active_profile_macros(self):
        """
        Carrega as macros do perfil ativo para as StringVar de UI
        E FORÇA A ATUALIZAÇÃO VISUAL DOS WIDGETS ScrolledText.
        """
        # Carrega os dados do arquivo específico do perfil
        macros = self.get_current_profile_macros()

        for i in range(9):
            macro_text = macros[i]
            self.devolutivas_contents[i].set(macro_text) # Atualiza a StringVar (para Hotkey)
            
            # ATUALIZAÇÃO VISUAL CRÍTICA:
            if self._gui_ready and len(self.devolutivas_text_widgets) > i:
                widget = self.devolutivas_text_widgets[i]
                widget.delete('1.0', tk.END) # Limpa o conteúdo atual
                widget.insert(tk.END, macro_text) # Insere o novo conteúdo
        
    def switch_profile(self, event=None):
        """Muda o perfil ativo e recarrega as macros na UI."""
        # O Combobox já alterou self.devolutivas_active_profile_name.
        
        # 1. O salvamento do perfil anterior é feito implicitamente pelo FocusOut da macro
        #    anterior. Se o usuário apenas trocou a combo, o último FocusOut deve ter salvo.
        
        # 2. Carrega o novo perfil na interface
        self.load_active_profile_macros()
        
        # 3. Salva a configuração de qual perfil está ativo (para persistência)
        self.salvar_json(ARQUIVO_DEVOLUTIVAS_CONFIG, {"active_profile": self.devolutivas_active_profile_name.get()})

        first_name = self._get_first_name()
        self.atualizar_status(f"Perfil de Devolutivas alterado para '{self.devolutivas_active_profile_name.get()}'. Pronto para agilizar, {first_name}!")
    
    def salvar_devolutivas_file(self):
        """Salva as 9 macros do perfil ATIVO diretamente no seu arquivo JSON."""
        active_name = self.devolutivas_active_profile_name.get()
        filepath = get_profile_filepath(active_name)
        
        current_macros = [var.get() for var in self.devolutivas_contents]
        data = {"macros": current_macros}

        if self.salvar_json(filepath, data):
            return True
        return False
        
    def add_new_profile(self):
        """Adiciona um novo perfil de devolutiva."""
        new_name = simpledialog.askstring("Novo Perfil", "Nome para o novo Perfil de Devolutivas:")
        if not new_name or not new_name.strip(): return
        
        new_name = new_name.strip()
        
        # Verifica se já existe um arquivo com esse nome
        if get_profile_filepath(new_name).exists():
            messagebox.showerror("Erro", f"O perfil '{new_name}' já existe. Tente um nome diferente.")
            return

        # 1. Salva o perfil ativo atual (se houver edição)
        self.salvar_devolutivas_file()
        
        # 2. Cria o novo arquivo de perfil vazio
        new_profile_macros = [""] * 9
        self.salvar_json(get_profile_filepath(new_name), {"macros": new_profile_macros})
        
        # 3. Atualiza a lista de nomes e muda para o novo perfil
        self.devolutivas_profiles = self._get_all_profile_names()
        self.devolutivas_active_profile_name.set(new_name)
        
        # 4. Força o Combobox a atualizar
        if hasattr(self, 'profile_combobox'):
            self.update_profile_combobox()
            
        self.load_active_profile_macros()
        
        # 5. Salva a configuração de qual perfil está ativo (para persistência)
        self.salvar_json(ARQUIVO_DEVOLUTIVAS_CONFIG, {"active_profile": new_name})
        self.atualizar_status(f"Novo perfil '{new_name}' criado e ativado. Agora é só preencher!")

    def remove_current_profile(self):
        """Remove o perfil ativo, excluindo seu arquivo JSON, exceto o perfil Padrão."""
        active_name = self.devolutivas_active_profile_name.get()
        # BLOQUEADO: Agora o único perfil que não pode ser removido é o "Personalizada"
        if active_name == "Personalizada":
            messagebox.showerror("Erro", "O perfil 'Personalizada' é essencial e não pode ser removido.")
            return
            
        if not messagebox.askyesno("Confirmar Remoção", f"Tem certeza que deseja remover o perfil '{active_name}'? Esta ação é irreversível e apagará todas as macros salvas nele."):
            return
            
        filepath_to_remove = get_profile_filepath(active_name)

        if os.path.exists(filepath_to_remove):
             try:
                 os.remove(filepath_to_remove)
             except Exception as e:
                 messagebox.showerror("Erro de Remoção", f"Não foi possível remover o arquivo: {e}")
                 return
        
        # 1. Atualiza a lista de perfis disponíveis
        self.devolutivas_profiles = self._get_all_profile_names()
        
        # 2. Volta para o perfil Personalizada e o ativa
        self.devolutivas_active_profile_name.set("Personalizada")

        if hasattr(self, 'profile_combobox'):
            self.update_profile_combobox()
            
        self.load_active_profile_macros() 
        
        # 3. Salva a configuração de qual perfil está ativo
        self.salvar_json(ARQUIVO_DEVOLUTIVAS_CONFIG, {"active_profile": self.devolutivas_active_profile_name.get()})
        
        self.atualizar_status(f"Perfil '{active_name}' removido. Voltamos ao Perfil Personalizada.")

    def update_profile_combobox(self):
        """Atualiza a lista de nomes no Combobox."""
        if hasattr(self, 'profile_combobox'):
            # Lista os perfis novamente, caso algum tenha sido adicionado/removido
            self.devolutivas_profiles = self._get_all_profile_names() 
            
            self.profile_combobox['values'] = self.devolutivas_profiles
            current_active = self.devolutivas_active_profile_name.get()
            
            if current_active in self.devolutivas_profiles:
                 self.profile_combobox.set(current_active)
            else:
                 # Fallback seguro (deve ser "Personalizada")
                 fallback_name = self.devolutivas_profiles[0] if self.devolutivas_profiles else "Personalizada"
                 self.devolutivas_active_profile_name.set(fallback_name)
                 self.profile_combobox.set(fallback_name)
            
    # --- Fim Funções de Perfil de Devolutivas ---


    # --- Funções de Restauração e Limpeza ---
    def confirmar_restauracao(self):
        aviso = ("ATENÇÃO, [Image of warning icon] VOCÊ ESTÁ PRESTES A ZERAR SEU SMARTBPO.\n\n"
                 "ISSO VAI APAGAR:\n"
                 "- Todos os Perfis de Devolutivas (e suas macros)\n"
                 "- Seus Registros de Agendas, Volumetria e Histórico da Calculadora\n"
                 "- Seu Perfil (Nome, Time) e Metas\n\n"
                 "ISSO VAI MANTER:\n"
                 "- Links Salvos na aba Consulta\n\n"
                 "Você tem certeza absoluta que deseja apagar todos os dados de uso e recomeçar?")
        if messagebox.askyesno("CONFIRMAR RESTAURAÇÃO DE DADOS", aviso):
            self.restaurar_padroes_originais()

    def _reset_gui_elements(self):
        """Força a redefinição visual e dos dados de trabalho na GUI."""
        
        self.devolutivas_active_profile_name.set("Personalizada") # Reverte para o padrão inicial
        if hasattr(self, 'profile_combobox'):
            self.update_profile_combobox() # Atualiza a lista do combo
            
        self.load_active_profile_macros() # Carrega o perfil ativo na UI

        self.vol_data_var.set(date.today().strftime(DATA_FORMATO_CURTO))
        self.vol_volume_var.set("")
        self.vol_notas_var.set("")
        
        self.vol_live_counter.set(0) # Reset do novo contador
        self.vol_live_counter_display_var.set("0") # Reset do novo contador
        
        self.calc_display_var.set("")
        if hasattr(self, 'anotacoes_text'): 
            self.anotacoes_text.delete('1.0', tk.END)
            self.anotacoes_gerais_var.set("")
        
        self.update_calc_history_display()
        self.atualizar_treeview_volumetria()
        
        # Força a recriação da aba Agendas para atualizar o painel da Daily
        self._agendas_initialized = False 
        if self.notebook.tab(self.notebook.select(), "text") == "Agendas":
            self.criar_aba_agendas()
            self._agendas_initialized = True
        
        self.atualizar_lista_links()
        
    def restaurar_padroes_originais(self):
        """Apaga os arquivos de dados selecionados e reinicia o estado do app."""
        
        # 1. Apaga os arquivos de dados principais
        arquivos_a_apagar = [
            ARQUIVO_DEVOLUTIVAS_CONFIG, ARQUIVO_VOLUMETRIA, ARQUIVO_CALCULADORA, 
            ARQUIVO_AGENDAS, ARQUIVO_CONFIG, ARQUIVO_FLAG_INIT, ARQUIVO_ANOTACOES,
        ]
        
        for arq in arquivos_a_apagar:
            if os.path.exists(arq):
                try: os.remove(arq)
                except Exception as e: print(f"Erro ao remover arquivo {arq}: {e}")

        # 2. Apaga todos os arquivos de perfis
        for file in DATA_DIR.glob('macros_*.json'):
            try:
                os.remove(file)
            except Exception as e:
                print(f"Erro ao remover arquivo de perfil {file.name}: {e}")
        
        temp_links = self.links_data[:] 
        
        self._initialize_state_variables() 
        
        self.links_data = temp_links
        self.salvar_json(ARQUIVO_LINKS, self.links_data)
        
        self.carregar_dados_iniciais() 
        self._reset_gui_elements()
        
        if hasattr(self, 'status_var'):
             self.atualizar_status("Dados restaurados! Reinicie o SmartBPO para começar a usar do zero.")
        
        if self.config_window: self.config_window.destroy()
        if self.metas_window: self.metas_window.destroy()
        if self.standard_calc_window: self.standard_calc_window.destroy()
        self.after(500, self.on_closing)

    # --- Funções de Hotkey (Threading) ---
    def iniciar_thread_atalhos(self):
        """Configura os atalhos globais de teclado usando a biblioteca 'keyboard'."""
        for i in range(1, 10):
            keyboard.add_hotkey(f'ctrl+{i}', self.hotkey_handler, args=(i, 'devolutiva'))

        keyboard.add_hotkey('ctrl+0', self.hotkey_handler, args=(0, 'cpf'))
        keyboard.add_hotkey('ctrl+alt+0', self.hotkey_handler, args=(0, 'cnpj'))
        
        # ATALHO ALTERADO: De 'ctrl+alt+e' para 'ctrl+alt+d'
        keyboard.add_hotkey('ctrl+alt+d', self.hotkey_handler, args=(0, 'hints'))
        
        self.atualizar_status("Atalhos globais de teclado ativados. Use para agilizar o trabalho!")

    def hotkey_handler(self, index, type):
        """Gerencia a ação a ser executada pelo atalho de teclado."""
        if not self.app_rodando: return 

        if type == 'devolutiva':
            try:
                # O texto é pego da StringVar ativa, que reflete o perfil ativo
                texto = self.devolutivas_contents[index - 1].get()
                if not texto.strip(): return
                self.after(0, lambda: self.executar_colagem_thread(texto, f"Ctrl+{index}"))
            except IndexError:
                print(f"Índice de devolutiva {index} inválido.")
        
        elif type == 'cpf':
            self.after(0, lambda: self.executar_colagem_thread("CPF: ", "Ctrl+0"))
        
        elif type == 'cnpj':
            self.after(0, lambda: self.executar_colagem_thread("CNPJ: ", "Ctrl+Alt+0"))
            
        elif type == 'hints':
            self.after(0, self.show_devolutiva_hints)

    def executar_colagem_thread(self, texto, atalho):
        """Inicia uma nova thread para executar a colagem do pyautogui, evitando bloqueio da GUI."""
        threading.Thread(target=self._run_pyautogui_paste, args=(texto, atalho), daemon=True).start()

    def _run_pyautogui_paste(self, texto, atalho):
        """
        (Roda em Thread Separada) Copia o texto para o clipboard e usa Ctrl+V para colar.
        """
        try:
            self.after(0, self.iconify)
            
            # 1. Copia o texto para a área de transferência
            pyperclip.copy(texto)
            
            # 2. Aumenta o tempo de espera para garantir que a janela alvo tenha foco
            time.sleep(0.3) 
            
            # 3. Simula a colagem (Ctrl+V)
            pyautogui.hotkey('ctrl', 'v')
            
            time.sleep(0.1)
            
            first_name = self._get_first_name()
            self.after(0, lambda: self.atualizar_status(f"Texto colado via {atalho}! Agilidade na ponta dos seus dedos, {first_name}."))
            
        except Exception as e:
            self.after(0, lambda: self.atualizar_status(f"Ops, erro na colagem (thread): {e}"))
            self.after(0, self.deiconify) 

    # --- Aba 1: Devolutivas (Lógica de Colagem/Hotkey) ---
    def criar_aba_devolutivas(self):
        """Cria todos os widgets da Aba 1, com foco no redimensionamento correto."""
        tab_devolutivas = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab_devolutivas, text="Devolutivas")
        
        frame_devolutivas_main = ttk.Frame(tab_devolutivas)
        frame_devolutivas_main.pack(fill="both", expand=True)

        # --- SELEÇÃO E GERENCIAMENTO DE PERFIL ---
        frame_perfil_manager = ttk.Frame(frame_devolutivas_main)
        frame_perfil_manager.pack(fill="x", pady=(0, 10))
        
        ttk.Label(frame_perfil_manager, text="Perfil Ativo:", font=("Segoe UI", 10, "bold"), foreground=PRIMARY_BLUE).pack(side=tk.LEFT, padx=(0, 10))
        
        self.profile_combobox = ttk.Combobox(
            frame_perfil_manager, 
            textvariable=self.devolutivas_active_profile_name,
            state="readonly",
            width=20
        )
        self.profile_combobox.pack(side=tk.LEFT, padx=(0, 15))
        self.profile_combobox.bind("<<ComboboxSelected>>", self.switch_profile)
        
        # MOVIMENTO: Atualiza o combobox aqui, após sua criação, para garantir que a lista de perfis seja preenchida.
        self.update_profile_combobox() 
        
        # --- AJUDA ---
        lbl_ajuda_dev = ttk.Label(
            frame_devolutivas_main, 
            text="Suas macros são salvas automaticamente. Use Ctrl+1 a Ctrl+9 para colar instantaneamente em qualquer lugar!", 
            font=("Segoe UI", 9, "italic"), 
            foreground="gray"
        )
        lbl_ajuda_dev.pack(pady=(5, 15), anchor="w")

        self.devolutivas_text_widgets = [] 

        frame_scroll_dev = ttk.Frame(frame_devolutivas_main)
        frame_scroll_dev.pack(fill="both", expand=True, pady=5)
        
        canvas_dev = tk.Canvas(frame_scroll_dev, bg="#FFFFFF", highlightthickness=0)
        scrollbar_dev = ttk.Scrollbar(frame_scroll_dev, orient="vertical", command=canvas_dev.yview)
        frame_lista_dev = ttk.Frame(canvas_dev, padding=5, style="TFrame")

        canvas_id = canvas_dev.create_window((0, 0), window=frame_lista_dev, anchor="nw") 
        
        frame_lista_dev.bind("<Configure>", 
                             lambda e: canvas_dev.configure(scrollregion=canvas_dev.bbox("all")))
        
        canvas_dev.configure(yscrollcommand=scrollbar_dev.set)
        canvas_dev.pack(side="left", fill="both", expand=True)
        scrollbar_dev.pack(side="right", fill="y")
        
        # Força o frame interno a esticar horizontalmente
        canvas_dev.bind('<Configure>', 
                        lambda e: canvas_dev.itemconfig(canvas_id, width=e.width))

        for i in range(9):
            self._create_devolutiva_widget(frame_lista_dev, i)

        frame_comandos = ttk.LabelFrame(frame_devolutivas_main, text="Atalhos Rápidos Essenciais", style="TLabelframe")
        # Ajustado o padding vertical
        frame_comandos.pack(fill="x", pady=(10, 5), ipady=5) 

        frame_comandos_internos = ttk.Frame(frame_comandos, padding=10)
        frame_comandos_internos.pack(fill="x")
        
        # Coluna 0 vai conter todos os elementos (atalhos e botões), alinhados à esquerda (w)
        frame_comandos_internos.columnconfigure(0, weight=1) 
        
        # --- 1. Frame de Atalhos (Lista) ---
        frame_atalhos = ttk.Frame(frame_comandos_internos, padding=(0, 5))
        frame_atalhos.grid(row=0, column=0, sticky="w", padx=10, pady=5) 
        
        fonte_atalho = ("Segoe UI", 10, "bold")
        frame_atalhos.columnconfigure(0, minsize=150)

        ttk.Label(frame_atalhos, text="Função", font=fonte_atalho).grid(row=0, column=0, sticky="w")
        ttk.Label(frame_atalhos, text="Atalho", font=fonte_atalho).grid(row=0, column=1, sticky="w", padx=15)
        
        ttk.Label(frame_atalhos, text="Colar 'CPF:'", font=fonte_atalho).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(frame_atalhos, text="Ctrl + 0", foreground=PRIMARY_BLUE).grid(row=1, column=1, sticky="w", padx=15, pady=2)
        
        ttk.Label(frame_atalhos, text="Colar 'CNPJ:'", font=fonte_atalho).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(frame_atalhos, text="Ctrl + Alt + 0", foreground=PRIMARY_BLUE).grid(row=2, column=1, sticky="w", padx=15, pady=2)
        
        ttk.Label(frame_atalhos, text="Mostrar Dicas", font=fonte_atalho).grid(row=3, column=0, sticky="w", pady=2)
        # ATALHO ATUALIZADO NO RÓTULO
        ttk.Label(frame_atalhos, text="Ctrl + Alt + D", foreground=PRIMARY_BLUE).grid(row=3, column=1, sticky="w", padx=15, pady=2)


    def _create_devolutiva_widget(self, parent, index):
        """Cria e configura um ScrolledText de devolutiva, otimizado para preenchimento de largura."""
        frame_linha = ttk.Frame(parent, padding=4, style="TFrame")
        
        frame_linha.columnconfigure(1, weight=1) 
        
        lbl_num = ttk.Label(frame_linha, text=f"Ctrl+{index+1}", font=("Segoe UI", 11, "bold"), foreground=PRIMARY_BLUE)
        lbl_num.grid(row=0, column=0, padx=(0, 10), sticky=tk.N+tk.W) 
        
        text_widget = scrolledtext.ScrolledText(
            frame_linha, 
            wrap=tk.WORD, 
            height=2,
            font=("Segoe UI", 10), 
            relief="flat", 
            borderwidth=1, 
            highlightbackground="#DDDDDD",
            bg=LIGHT_BLUE 
        )
        text_widget.grid(row=0, column=1, sticky="ew", padx=10, ipady=4)
        self.devolutivas_text_widgets.append(text_widget)
        
        # Insere o conteúdo inicial da StringVar ativa
        text_widget.insert(tk.END, self.devolutivas_contents[index].get())
        
        # Atualiza a StringVar (que é o que a hotkey usa)
        text_widget.bind("<KeyRelease>", lambda e, var=self.devolutivas_contents[index]: self.update_devolutiva_content(e, var))
        text_widget.bind("<FocusOut>", lambda e, var=self.devolutivas_contents[index]: self.update_devolutiva_content(e, var, save_to_file=True))

        
        btn_colar = ttk.Button(
            frame_linha, 
            text="Colar Agora", 
            command=lambda text_w=text_widget: self.executar_colagem(text_w.get('1.0', tk.END).strip())
        )
        btn_colar.grid(row=0, column=2, padx=10, sticky=tk.N+tk.E)
        
        frame_linha.pack(fill="x", expand=True, pady=4)

    def update_devolutiva_content(self, event, var, save_to_file=False):
        """Atualiza a StringVar a partir do ScrolledText e salva se for FocusOut."""
        try:
            content = event.widget.get('1.0', tk.END).strip()
            var.set(content)
            
            if save_to_file:
                # O FocusOut chama o salvamento no arquivo para persistir
                self.salvar_devolutivas_file() 
                
        except Exception as e:
            print(f"Erro ao atualizar ScrolledText: {e}")

    def salvar_devolutivas(self):
        """Função unificada de salvamento, agora direciona para salvar no arquivo."""
        first_name = self._get_first_name()
        if self.salvar_devolutivas_file():
            self.atualizar_status(f"Suas devolutivas do perfil '{self.devolutivas_active_profile_name.get()}' foram salvas! Excelente, {first_name}!")
        else:
             self.atualizar_status(f"Ops! Tivemos um erro ao salvar suas devolutivas. Tente novamente.")


    def executar_colagem(self, texto):
        """Inicia a colagem via thread (usada por botões)."""
        self.executar_colagem_thread(texto, "Botão")

    def selecionar_e_copiar_linha(self):
        """Simula as ações para selecionar e copiar uma linha inteira."""
        try:
            self.iconify()
            time.sleep(0.5)
            pyautogui.press('home')
            pyautogui.keyDown('shift')
            pyautogui.press('end')
            pyautogui.keyUp('shift')
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.1)
            self.deiconify()
            self.atualizar_status("Linha selecionada e copiada com sucesso!")
        except Exception as e:
            self.atualizar_status(f"Ops! Erro ao copiar a linha: {e}")
            if not self.winfo_exists(): self.deiconify()
    
    def show_devolutiva_hints(self):
        """Cria e exibe um popup temporário com a lista de devolutivas."""
        if self.popup_hints and self.popup_hints.winfo_exists():
            self.popup_hints.destroy()
            self.popup_hints = None
            return

        self.popup_hints = tk.Toplevel(self)
        self.popup_hints.title(f"Dicas Rápidas - Perfil: {self.devolutivas_active_profile_name.get()}")
        self.popup_hints.overrideredirect(True)
        self.popup_hints.attributes('-topmost', True) 
        self.popup_hints.configure(background=PRIMARY_BLUE) 

        # Adiciona um novo estilo para o popup
        self.style.configure("Popup.TFrame", background="#FFFFFF", borderwidth=1, relief="solid")
        
        frame = ttk.Frame(self.popup_hints, style="Popup.TFrame") 
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        # CÓDIGO CORRIGIDO: Removido o atalho da string do título, mantendo apenas "DICAS RÁPIDAS"
        lbl_header = tk.Label(frame, text=f"DICAS RÁPIDAS - Perfil: {self.devolutivas_active_profile_name.get()}", 
                  font=("Segoe UI", 11, "bold"), background=PRIMARY_BLUE, foreground="white")
        lbl_header.pack(pady=(0, 8), anchor="w", fill="x", ipady=5)
        
        fundo_conteudo = "#FFFFFF" 
        
        for i in range(9):
            atalho = f"Ctrl+{i+1}"
            texto_completo = self.devolutivas_contents[i].get() 
            texto_exibicao = texto_completo.replace('\n', ' / ') 
            if len(texto_exibicao) > 60: texto_exibicao = texto_exibicao[:57] + "..."
            linha = f"{atalho}: {texto_exibicao}"
            
            lbl = tk.Label(frame, text=linha, anchor="w", justify=tk.LEFT, 
                           font=("Segoe UI", 9), background=fundo_conteudo, foreground=PRIMARY_BLUE, padx=10, pady=3, relief="flat")
            lbl.pack(fill="x", pady=(1,1))

        self.popup_hints.update_idletasks()
        width = self.popup_hints.winfo_reqwidth()
        height = self.popup_hints.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        
        self.popup_hints.geometry(f'+{x}+{y}')
        self.after(5000, self.hide_devolutiva_hints)

    def hide_devolutiva_hints(self):
        if self.popup_hints and self.popup_hints.winfo_exists():
            self.popup_hints.destroy()
            self.popup_hints = None
            

    # --- Aba 2: Consulta (Links) ---

    def _get_icon_for_link(self, name):
        """Retorna o emoji do ícone baseado no nome do link."""
        name_lower = name.lower()
        if "senior" in name_lower: return LINK_ICONS["senior"]
        if "receita" in name_lower: return LINK_ICONS["receita"]
        if "simples" in name_lower: return LINK_ICONS["simples"]
        if "validar" in name_lower: return LINK_ICONS["validar"]
        return LINK_ICONS["geral"]

    def criar_aba_consulta(self):
        """Cria todos os widgets da Aba 2. Otimizado: Layout centralizado com ícones."""
        tab_consulta = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab_consulta, text="Consulta")
        
        lbl_ajuda_cons = ttk.Label(tab_consulta, text="Acesse rapidamente seus links de consulta. Use o menu Configuração para gerenciar seus favoritos.", font=("Segoe UI", 9, "italic"), foreground="gray")
        lbl_ajuda_cons.pack(pady=(0, 15), anchor="w")

        frame_links_center = ttk.Frame(tab_consulta)
        frame_links_center.pack(fill="both", expand=True, pady=10)
        
        frame_tabela_links = ttk.LabelFrame(frame_links_center, text="Links Salvos", style="TLabelframe")
        frame_tabela_links.pack(expand=True, fill="both", padx=5) 
        
        cols = ("Ícone", "Nome", "URL (oculta)")
        self.tree_links = ttk.Treeview(frame_tabela_links, columns=cols, show="headings", style="Treeview")
        
        self.tree_links.heading("Ícone", text="")
        self.tree_links.heading("Nome", text="NOME DO LINK", anchor="center") 
        self.tree_links.heading("URL (oculta)", text="") 
        
        self.tree_links.column("Ícone", width=50, anchor="center", stretch=tk.NO)
        self.tree_links.column("Nome", width=500, anchor="w", stretch=tk.YES)
        self.tree_links.column("URL (oculta)", width=0, minwidth=0, stretch=tk.NO) 
        
        # Adiciona um bind de duplo clique para abrir o link
        self.tree_links.bind("<Double-1>", lambda e: self.abrir_link_selecionado())


        scrollbar_links = ttk.Scrollbar(frame_tabela_links, orient="vertical", command=self.tree_links.yview)
        self.tree_links.configure(yscrollcommand=scrollbar_links.set)
        
        scrollbar_links.pack(side=tk.RIGHT, fill="y")
        self.tree_links.pack(side=tk.TOP, fill="both", expand=True, padx=10, pady=10)
        
        btn_abrir_link_sel = ttk.Button(frame_links_center, text="Abrir Link Selecionado", command=self.abrir_link_selecionado)
        btn_abrir_link_sel.pack(fill="x", ipady=8, pady=(15,0), padx=5)

    def abrir_link_url(self, url):
        """Abre um URL no navegador padrão."""
        try:
            if not url.startswith("http://") and not url.startswith("https://"):
                 url = "http://" + url
            webbrowser.open_new_tab(url)
            self.atualizar_status(f"Abrindo link: {url[:30]}...")
        except Exception as e:
            self.atualizar_status(f"Ops! Erro ao tentar abrir o link: {e}")

    def atualizar_lista_links(self):
        """Atualiza a Treeview de links com ícones."""
        if not hasattr(self, 'tree_links'):
            return 
            
        for i in self.tree_links.get_children():
            self.tree_links.delete(i)
        
        for link in self.links_data:
            icon = self._get_icon_for_link(link['nome'])
            self.tree_links.insert("", tk.END, values=(icon, link['nome'], link['url']))

    def adicionar_link(self):
        """Adiciona um novo link (Chamado pelo Menu)."""
        nome = simpledialog.askstring("Novo Link", "Qual o nome deste link?")
        if not nome: return
        url = simpledialog.askstring("Novo Link", f"Cole a URL (link) para '{nome}':")
        if not url: return
        
        first_name = self._get_first_name()

        self.links_data.append({"nome": nome, "url": url})
        self.atualizar_lista_links()
        self.salvar_json(ARQUIVO_LINKS, self.links_data)
        self.atualizar_status(f"Link '{nome}' adicionado! Mais uma ferramenta no seu arsenal, {first_name}!")

    def remover_link(self):
        """Remove o link selecionado (Chamado pelo Menu)."""
        try:
            selected_item = self.tree_links.selection()[0]
            nome = self.tree_links.item(selected_item, 'values')[1]
            
            first_name = self._get_first_name()
            
            if messagebox.askyesno("Confirmar", f"Tem certeza que deseja remover o link '{nome}'?"):
                self.links_data = [link for link in self.links_data if link['nome'] != nome]
                self.atualizar_lista_links()
                self.salvar_json(ARQUIVO_LINKS, self.links_data)
                self.atualizar_status(f"Link '{nome}' removido. Próximo, {first_name}!")
        except IndexError:
            self.atualizar_status("Ops! Ninguém foi selecionado. Escolha um link para remover.")
        except Exception as e:
            self.atualizar_status(f"Erro ao remover link: {e}")


    def abrir_link_selecionado(self):
        """Abre o link selecionado da lista."""
        try:
            selected_item = self.tree_links.selection()[0]
            item_values = self.tree_links.item(selected_item, 'values')
            url = item_values[2] 
            self.abrir_link_url(url)
        except IndexError:
            self.atualizar_status("Por favor, selecione um link para abrir!")

    # --- Aba 3: Calculadora ---
    
    # REMOVIDO: update_calc_notes_var (movido para a aba Anotações)
    
    def update_calc_history_display(self):
        """Atualiza a Listbox do histórico de cálculos."""
        # Esta função é chamada para atualizar o histórico, mas o widget só existe no pop-up.
        # Se o pop-up não estiver aberto, não faz nada.
        if not self.calc_history:
            return
        
        # Se o pop-up estiver aberto, atualiza a listbox
        if hasattr(self, 'standard_calc_window') and self.standard_calc_window and hasattr(self, 'listbox_history'):
            self.listbox_history.delete(0, tk.END)
            for item in self.calc_history[-50:]:
                self.listbox_history.insert(tk.END, item)
            self.listbox_history.see(tk.END)
        
    def clear_calc_history_and_notes(self):
        """Limpa o histórico de cálculos e o campo de anotações."""
        first_name = self._get_first_name()
        
        if messagebox.askyesno("Confirmar Limpeza", f"Atenção! Você quer mesmo limpar todo o histórico de cálculos e suas anotações?"):
            self.calc_history = []
            
            # Limpa anotações na aba Anotações
            self.anotacoes_gerais_var.set(self.carregar_anotacoes_padrao().get("anotacoes"))
            if hasattr(self, 'anotacoes_text'): 
                self.anotacoes_text.delete('1.0', tk.END)
                self.anotacoes_text.insert(tk.END, self.anotacoes_gerais_var.get())
            
            # Salva a limpeza das anotações
            self._save_anotacoes_file()

            # Limpa histórico e display da janela pop-up (se aberta)
            if hasattr(self, 'standard_calc_window') and self.standard_calc_window and self.standard_calc_window.winfo_exists():
                self.calc_display_var.set("")
                self.update_calc_history_display() # Limpa a listbox

            self.atualizar_status(f"Histórico e anotações limpos! Espaço renovado, {first_name}!")


    def criar_aba_calculadora(self,):
        """Cria todos os widgets da Aba 3: Simples Nacional e Botão Pop-up."""
        tab_calculadora = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab_calculadora, text="Calculadora")
        
        tab_calculadora.columnconfigure(0, weight=1)
        tab_calculadora.rowconfigure(0, weight=1)

        # --- Frame de Scroll (Canvas) para a calculadora ---
        frame_scroll_calc = ttk.Frame(tab_calculadora)
        frame_scroll_calc.grid(row=0, column=0, sticky="nsew") 
        
        canvas_calc = tk.Canvas(frame_scroll_calc, bg=BACKGROUND_GRAY, highlightthickness=0)
        scrollbar_calc = ttk.Scrollbar(frame_scroll_calc, orient="vertical", command=canvas_calc.yview)
        
        calc_main_frame = ttk.Frame(canvas_calc, style="TFrame")
        
        canvas_calc.configure(yscrollcommand=scrollbar_calc.set)
        
        scrollbar_calc.pack(side="right", fill="y")
        canvas_calc.pack(side="left", fill="both", expand=True)

        canvas_id = canvas_calc.create_window((0, 0), window=calc_main_frame, anchor="nw")
        
        calc_main_frame.bind("<Configure>", 
                             lambda e: canvas_calc.configure(scrollregion=canvas_calc.bbox("all")))
        
        canvas_calc.bind('<Configure>', 
                         lambda e: canvas_calc.itemconfig(canvas_id, width=e.width))
        
        # Layout principal da aba: Botão (row 0), Simples Nacional (row 1)
        calc_main_frame.columnconfigure(0, weight=1) 
        calc_main_frame.rowconfigure(1, weight=1) # Faz o Simples Nacional expandir verticalmente
        
        # 1. Botão para Calculadora Padrão (Fica no topo)
        frame_botoes_aba = ttk.Frame(calc_main_frame)
        frame_botoes_aba.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 10))
        frame_botoes_aba.columnconfigure(0, weight=1) # Faz o botão ocupar toda a largura
        
        btn_popup_calc = ttk.Button(frame_botoes_aba, text="🔢 Abrir Calculadora Padrão", command=self.show_standard_calculator_window)
        btn_popup_calc.grid(row=0, column=0, sticky="ew", ipady=8)
        
        # 2. Calculadora do Simples Nacional
        self.criar_calc_simples(calc_main_frame)
        
        # Anotações foram removidas daqui


    def show_standard_calculator_window(self):
        """Cria e exibe a calculadora padrão em uma nova janela Toplevel, com botão de limpeza."""
        if hasattr(self, 'standard_calc_window') and self.standard_calc_window and self.standard_calc_window.winfo_exists():
            self.standard_calc_window.lift()
            return
            
        self.standard_calc_window = tk.Toplevel(self)
        self.standard_calc_window.title("Calculadora Padrão (Pop-up)")
        self.standard_calc_window.transient(self)
        self.standard_calc_window.grab_set() 
        # CORREÇÃO: Permite redimensionamento horizontal e vertical
        self.standard_calc_window.resizable(True, True) 
        self.standard_calc_window.protocol("WM_DELETE_WINDOW", self.standard_calc_window.destroy) 
        
        frame_calc_padrao = ttk.Frame(self.standard_calc_window, padding=15, style="TLabelframe")
        frame_calc_padrao.pack(fill="both", expand=True)
        
        # 1. Display
        calc_display = ttk.Entry(frame_calc_padrao, textvariable=self.calc_display_var, font=("Consolas", 18, "bold"), justify="right", style="Custom.TEntry")
        calc_display.grid(row=0, column=0, columnspan=4, pady=10, padx=10, sticky="ew", ipady=5)
        calc_display.bind('<Return>', lambda e: self.calc_equals())
        
        # 2. Buttons
        frame_botoes = ttk.Frame(frame_calc_padrao)
        frame_botoes.grid(row=1, column=0, columnspan=4, sticky="ew", padx=5) 

        for i in range(4): frame_botoes.rowconfigure(i, weight=1)
        for i in range(4): frame_botoes.columnconfigure(i, weight=1)

        botoes = ['7', '8', '9', '/', '4', '5', '6', '*', '1', '2', '3', '-', '0', '.', 'C', '+']
        
        row, col = 0, 0
        for texto_btn in botoes:
            if texto_btn == 'C':
                cmd = lambda: self.calc_clear()
            else:
                cmd = lambda t=texto_btn: self.calc_button_click(t)
            
            btn = ttk.Button(frame_botoes, text=texto_btn, command=cmd)
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            col += 1
            if col > 3: col = 0; row += 1

        btn_equals = ttk.Button(frame_botoes, text="=", command=self.calc_equals)
        btn_equals.grid(row=4, column=0, columnspan=4, padx=3, pady=3, sticky="nsew")

        # 3. History Listbox 
        frame_hist = ttk.Frame(frame_calc_padrao)
        # Permite que o histórico se expanda verticalmente
        frame_hist.grid(row=5, column=0, columnspan=4, padx=5, pady=(20, 5), sticky="nsew")
        # Garante que a linha 5 do grid do frame_calc_padrao (onde está o histórico) se expanda
        frame_calc_padrao.grid_rowconfigure(5, weight=1) 
        
        # Botão Limpar Histórico (Removido da aba principal, adicionado no pop-up)
        frame_title_clear = ttk.Frame(frame_hist)
        frame_title_clear.pack(fill="x", anchor="w")
        frame_title_clear.columnconfigure(0, weight=1)
        
        ttk.Label(frame_title_clear, text="Histórico de Cálculos:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        
        btn_clear_hist = ttk.Button(
            frame_title_clear, 
            text="🗑️ Limpar", 
            command=self.clear_calc_history_and_notes, # Reutiliza a função
            width=10, 
            padding=[5, 2] 
        )
        btn_clear_hist.grid(row=0, column=1, sticky="e")
        
        listbox_frame = ttk.Frame(frame_hist)
        listbox_frame.pack(fill="both", expand=True)
        
        # Altura inicial reduzida (height=5) e a Listbox deve expandir (sticky="nsew")
        self.listbox_history = tk.Listbox(listbox_frame, font=("Consolas", 10), height=5, selectmode=tk.BROWSE, bg="#EFEFEF", fg="#333333", relief="flat", highlightthickness=0)
        scrollbar_hist = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.listbox_history.yview)
        self.listbox_history.configure(yscrollcommand=scrollbar_hist.set)
        
        scrollbar_hist.pack(side=tk.RIGHT, fill="y")
        self.listbox_history.pack(side=tk.LEFT, fill="both", expand=True)

        # Atualiza o histórico ao abrir (carrega dados salvos)
        self.update_calc_history_display()

        # Centralizando a janela pop-up e definindo o tamanho inicial (W=400, H=550)
        self.standard_calc_window.update_idletasks()
        # Tamanho inicial maior e confortável
        w = 400
        h = 550 
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        self.standard_calc_window.geometry(f'{w}x{h}+{x}+{y}') 


    def calc_button_click(self, number):
        self.calc_display_var.set(self.calc_display_var.get() + str(number))

    def calc_clear(self):
        self.calc_display_var.set("")

    def calc_equals(self):
        """
        Executa o cálculo e armazena no histórico, usando avaliação de expressão segura (ast.parse).
        Substitui o inseguro eval().
        """
        expression = self.calc_display_var.get().replace(' ', '').replace(',', '.') 
        
        if not expression:
            return

        try:
            tree = ast.parse(expression, mode='eval')
            result = safe_eval(tree.body) 
            result = round(result, 4)
            
            calc_entry = f"{self.calc_display_var.get()} = {str(result).replace('.', ',')}"
            
            if len(self.calc_history) >= 200:
                 self.calc_history.pop(0) 
            self.calc_history.append(calc_entry)
            
            # Atualiza o display da janela pop-up, se estiver aberta
            self.update_calc_history_display()
            self.calc_display_var.set(str(result).replace('.', ','))

        except (TypeError, SyntaxError) as e: 
            error_msg = str(e).split(': ')[-1] 
            self.calc_display_var.set("Erro")
            self.atualizar_status(f"Erro de cálculo: Expressão inválida ou insegura ({error_msg})")
        except ZeroDivisionError:
            self.calc_display_var.set("Erro")
            self.atualizar_status("Erro: Divisão por zero. Atenção a isso!")
        except Exception as e: 
            self.calc_display_var.set("Erro")
            self.atualizar_status(f"Erro inesperado no cálculo: {e}")

    def criar_calc_simples(self, parent):
        """Cria a calculadora do Simples Nacional.
           REVISADO: Layout otimizado para a aba principal."""
        frame_calc_simples = ttk.LabelFrame(parent, text="Calculadora do Simples Nacional", style="TLabelframe")
        # Ocupa a primeira linha e a largura total da coluna principal da aba
        frame_calc_simples.grid(row=1, column=0, padx=10, pady=10, sticky="ew") # MUDADO PARA ROW 1 (abaixo do botão pop-up)
        
        # Container interno para usar pack/grid com mais liberdade
        inner_frame = ttk.Frame(frame_calc_simples)
        inner_frame.pack(fill="both", expand=True)
        
        # 1. Cenário
        frame_cenario = ttk.Frame(inner_frame)
        frame_cenario.pack(fill="x", pady=10)
        ttk.Label(frame_cenario, text="1. Escolha o Cenário:", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        
        frame_radio = ttk.Frame(frame_cenario)
        radio_mais_12 = ttk.Radiobutton(frame_radio, text="Empresa > 12 meses", variable=self.cenario_var, value=">12m", command=self.atualizar_interface_simples)
        radio_menos_12 = ttk.Radiobutton(frame_radio, text="Empresa < 12 meses", variable=self.cenario_var, value="<12m", command=self.atualizar_interface_simples)
        radio_mais_12.pack(side=tk.LEFT, padx=15)
        radio_menos_12.pack(side=tk.LEFT, padx=15)
        frame_radio.pack(anchor="w", pady=10)
        
        # 2. Campos
        ttk.Label(inner_frame, text="2. Preencha os Campos:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(20,10))
        
        # Layout de GRID para os campos de entrada
        
        # Cenário > 12m
        frame_cenario_mais_12 = ttk.Frame(inner_frame)
        self.frame_cenario_mais_12 = frame_cenario_mais_12
        
        # Corrigido: A coluna 0 (rótulos) agora tem um peso maior (2) e a coluna 1 (entradas) tem peso 3.
        # Isso garante que os rótulos tenham espaço suficiente para não serem cortados.
        frame_cenario_mais_12.columnconfigure(0, weight=2, minsize=200) # Aumentado o peso e o minsize
        frame_cenario_mais_12.columnconfigure(1, weight=3) 
        
        ttk.Label(frame_cenario_mais_12, text="RBT12 (Receita Bruta 12m):").grid(row=0, column=0, sticky="w", pady=8, padx=5)
        ttk.Entry(frame_cenario_mais_12, textvariable=self.simples_rbt12_var, style="Custom.TEntry").grid(row=0, column=1, sticky="ew", pady=8, padx=10, ipady=4)
        
        ttk.Label(frame_cenario_mais_12, text="RPA (Receita do Mês Atual):").grid(row=1, column=0, sticky="w", pady=8, padx=5)
        ttk.Entry(frame_cenario_mais_12, textvariable=self.simples_rpa_var, style="Custom.TEntry").grid(row=1, column=1, sticky="ew", pady=8, padx=10, ipady=4)
        
        ttk.Label(frame_cenario_mais_12, text="PAA (Receita Mês Antigo a Retirar):").grid(row=2, column=0, sticky="w", pady=8, padx=5)
        ttk.Entry(frame_cenario_mais_12, textvariable=self.simples_paa_var, style="Custom.TEntry").grid(row=2, column=1, sticky="ew", pady=8, padx=10, ipady=4)

        # Cenário < 12m
        frame_cenario_menos_12 = ttk.Frame(inner_frame)
        self.frame_cenario_menos_12 = frame_cenario_menos_12
        frame_cenario_menos_12.columnconfigure(0, weight=2, minsize=200) 
        frame_cenario_menos_12.columnconfigure(1, weight=3)
        
        ttk.Label(frame_cenario_menos_12, text="RBA Total (Soma RBT Acumulada):").grid(row=0, column=0, sticky="w", padx=5, pady=8)
        ttk.Entry(frame_cenario_menos_12, textvariable=self.simples_total_acumulado_var, style="Custom.TEntry").grid(row=0, column=1, sticky="ew", padx=10, pady=8, ipady=4)
        
        ttk.Label(frame_cenario_menos_12, text="Meses de Existência (1 a 11):").grid(row=1, column=0, sticky="w", padx=5, pady=8)
        ttk.Entry(frame_cenario_menos_12, textvariable=self.simples_meses_var, style="Custom.TEntry").grid(row=1, column=1, sticky="ew", padx=10, pady=8, ipady=4)
        
        self.atualizar_interface_simples() 
        
        btn_calcular_simples = ttk.Button(inner_frame, text="Calcular Simples", command=self.calcular_simples)
        btn_calcular_simples.pack(pady=10, ipady=5, fill="x", padx=5) 
        
        # 3. Resultados
        ttk.Label(inner_frame, text="3. Resultados:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(20,10))
        frame_resultados = ttk.Frame(inner_frame, padding=10)
        frame_resultados.pack(fill="x", expand=True)
        
        # Corrigido: Coluna de rótulos dos resultados também precisa de peso maior.
        frame_resultados.columnconfigure(0, weight=2, minsize=200)
        frame_resultados.columnconfigure(1, weight=3)

        # Usando rótulos mais descritivos nos resultados
        ttk.Label(frame_resultados, text="Média Móvel (RBT12 / 12):").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(frame_resultados, textvariable=self.res2_var, state="readonly", style="Result.TEntry").grid(row=0, column=1, sticky="ew", pady=5, padx=10, ipady=4) # Res2 é a média simples
        
        ttk.Label(frame_resultados, text="Base de Cálculo (RBTm):").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(frame_resultados, textvariable=self.res1_var, state="readonly", style="Result.TEntry").grid(row=1, column=1, sticky="ew", pady=5, padx=10, ipady=4) # Res1 é a média móvel ajustada
        
        ttk.Label(frame_resultados, text="Média Proporcional (< 12m):").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(frame_resultados, textvariable=self.res3_var, state="readonly", style="Result.TEntry").grid(row=2, column=1, sticky="ew", pady=5, padx=10, ipady=4)

    def formatar_moeda(self, valor):
        """Formata um valor float para string de moeda brasileira."""
        try:
            # Garante que o valor seja float antes de formatar
            valor = float(valor)
            # Utiliza f-string para formatação com substituição para vírgula
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception: 
            return "R$ 0,00"
            
    def _safe_get_float(self, var, field_name="Campo"):
        """Tenta obter o valor float de uma StringVar, tratando caracteres inválidos."""
        val_str = var.get().strip().replace('.', '').replace(',', '.')
        if not val_str: 
            return 0.0
        
        if not re.match(r'^-?\d+(\.\d+)?$', val_str):
            raise ValueError(f"'{field_name}' deve ser um valor numérico válido.")
            
        return float(val_str)

    def calcular_simples(self):
        """Otimização: Lógica do cálculo mais enxuta."""
        try:
            for var in self.resultados_vars.values(): var.set("")

            cenario = self.cenario_var.get()
            
            if cenario == ">12m":
                rbt12 = self._safe_get_float(self.simples_rbt12_var, "RBT12 (Receita Bruta 12m)")
                rpa = self._safe_get_float(self.simples_rpa_var, "RPA (Receita do Mês Atual)")
                paa = self._safe_get_float(self.simples_paa_var, "PAA (Receita Mês Antiga a Retirar)")
                
                # Média Móvel Ajustada (Base de Cálculo para Simples 12m)
                res1_val = (rbt12 + rpa - paa) / 12
                self.res1_var.set(self.formatar_moeda(res1_val))
                
                # Média Simples (RBT12 / 12)
                res2_val = rbt12 / 12
                self.res2_var.set(self.formatar_moeda(res2_val))
                
                # Zera o proporcional
                self.res3_var.set("")
                
            elif cenario == "<12m":
                rba_total = self._safe_get_float(self.simples_total_acumulado_var, "RBA Total (Soma RBT12 + RPA)")
                meses = self._safe_get_float(self.simples_meses_var, "Total Meses de Existência")
                
                if meses <= 0 or meses > 11: raise ValueError("Meses de existência deve ser entre 1 e 11.")
                
                # Média Proporcional: RBA Total / Meses
                res3_val = rba_total / meses
                self.res3_var.set(self.formatar_moeda(res3_val))
                
                # Zera os resultados > 12m
                self.res1_var.set("")
                self.res2_var.set("")
                
            self.atualizar_status("Cálculo do Simples realizado! Informação na mão.")
            
        except ValueError as ve: 
            self.atualizar_status(f"Erro no cálculo: {ve}")
        except ZeroDivisionError: 
            self.calc_display_var.set("Erro")
            self.atualizar_status("Erro: Divisão por zero. Atenção a isso!")
        except Exception as e: 
            self.calc_display_var.set("Erro")
            self.atualizar_status(f"Erro inesperado no cálculo: {e}")

    def atualizar_interface_simples(self):
        cenario = self.cenario_var.get()
        if cenario == ">12m":
            self.frame_cenario_mais_12.pack(fill="x", expand=True, pady=10)
            self.frame_cenario_menos_12.pack_forget()
        elif cenario == "<12m":
            self.frame_cenario_mais_12.pack_forget()
            self.frame_cenario_menos_12.pack(fill="x", expand=True, pady=10)


    # --- Aba 4: Volumetria ---
    
    # NEW: Live Counter Logic
    def increment_live_counter(self):
        """Incrementa o contador de fluxo em 1 e atualiza a exibição."""
        current_value = self.vol_live_counter.get()
        new_value = current_value + 1
        self.vol_live_counter.set(new_value)
        self.vol_live_counter_display_var.set(str(new_value))
        
    def decrement_live_counter(self):
        """Decrementa o contador de fluxo em 1, garantindo que não seja negativo."""
        current_value = self.vol_live_counter.get()
        if current_value > 0:
            new_value = current_value - 1
            self.vol_live_counter.set(new_value)
            self.vol_live_counter_display_var.set(str(new_value))
        else:
             self.atualizar_status("O contador já está zerado. Nada para remover!")
        
    def reset_live_counter(self):
        """Zera o contador de fluxo e atualiza a exibição."""
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja zerar o contador de fluxo atual?"):
            self.vol_live_counter.set(0)
            self.vol_live_counter_display_var.set("0")
            self.atualizar_status("Contador de fluxo zerado. Novo ciclo, novas conquistas!")

    def use_live_counter_as_volume(self):
        """Transfere o valor do contador em tempo real para o campo de Volume."""
        current_value = self.vol_live_counter.get()
        self.vol_volume_var.set(str(current_value))
        self.atualizar_status(f"Volume de {current_value} transferido. Agora é só registrar!")
    # END NEW

    def open_date_selection_calendar(self, master, v_data, entry_widget):
        """
        [MODIFICADO] Substitui o calendário externo pela entrada de texto simples 
        (simpledialog) com validação, eliminando o problema de foco do Toplevel.
        """
        current_value = v_data.get()
        
        # Usa simpledialog (que é bloqueante e mais seguro para foco)
        selected_date_str = simpledialog.askstring(
            "Selecionar Dia de Registro", 
            f"Digite a data no formato {DATA_DISPLAY_CURTO}:", 
            parent=master, 
            initialvalue=current_value
        )
        
        if selected_date_str:
            selected_date_str = selected_date_str.strip()
            # Valida o formato DD/MM
            if self._validate_date_format(selected_date_str, is_long_format=False):
                v_data.set(selected_date_str)
                # Tenta focar o widget de entrada novamente
                if entry_widget: entry_widget.focus()
            else:
                messagebox.showerror("Erro de Formato", f"Ops! Formato de data inválido. Use {DATA_DISPLAY_CURTO}.")
                # Se for inválido, o widget de entrada pode ser re-focado para correção manual
                if entry_widget: entry_widget.focus()
                
    # FIM: open_date_selection_calendar


    def criar_aba_volumetria(self):
        """Cria todos os widgets da Aba 5, incluindo o contador de fluxo.
           IMPLEMENTAÇÃO DE SCROLL: Todo o conteúdo é colocado dentro de um Canvas para permitir
           a rolagem vertical quando a janela é redimensionada."""
        tab_volumetria = ttk.Frame(self.notebook, padding=0) # Padding zero na raiz
        self.notebook.add(tab_volumetria, text="Volumetria") # ADD: Adicionado a linha que adiciona a aba ao notebook

        # --- Frame de Scroll (Canvas) ---
        frame_scroll_container = ttk.Frame(tab_volumetria)
        frame_scroll_container.pack(fill="both", expand=True)
        
        canvas_vol = tk.Canvas(frame_scroll_container, bg=BACKGROUND_GRAY, highlightthickness=0)
        scrollbar_vol_main = ttk.Scrollbar(frame_scroll_container, orient="vertical", command=canvas_vol.yview)
        
        # Frame principal que conterá todo o conteúdo da aba (e será redimensionado)
        # ADD: Padding de volta para os 15px originais para dar margem
        frame_vol_main = ttk.Frame(canvas_vol, padding=15)
        
        canvas_vol.configure(yscrollcommand=scrollbar_vol_main.set)
        
        scrollbar_vol_main.pack(side="right", fill="y")
        canvas_vol.pack(side="left", fill="both", expand=True)

        canvas_id = canvas_vol.create_window((0, 0), window=frame_vol_main, anchor="nw")
        
        # Atualiza a região de rolagem quando o frame_vol_main for configurado
        frame_vol_main.bind("<Configure>", 
                             lambda e: canvas_vol.configure(scrollregion=canvas_vol.bbox("all")))
        
        # Faz o frame interno esticar horizontalmente junto com o canvas
        canvas_vol.bind('<Configure>', 
                         lambda e: canvas_vol.itemconfig(canvas_id, width=e.width))
        
        # O frame_vol_main agora usa grid apenas para alinhar os blocos verticalmente
        frame_vol_main.columnconfigure(0, weight=1) 
        # Nenhuma row precisa de weight=1 aqui, pois o scrollbar cuida da expansão vertical.


        
        # --- 0. CONTADOR DE FLUXO EM TEMPO REAL (NOVO) ---
        frame_live_counter = ttk.LabelFrame(frame_vol_main, text="Contador de Fluxo (Dia Atual)", style="TLabelframe")
        # Usando grid com row=0 e sticky="ew" (preenchimento horizontal)
        frame_live_counter.grid(row=0, column=0, sticky="ew", padx=5, pady=5) 
        
        # Colunas internas para botões e display
        frame_live_counter.columnconfigure((0, 1, 2), weight=1) 

        # Display do Contador (Ocupa as 3 colunas)
        frame_display = ttk.Frame(frame_live_counter, padding=(10, 5))
        frame_display.grid(row=0, column=0, sticky="nsew", padx=10, pady=5, columnspan=3) 
        ttk.Label(frame_display, text="Fluxos Contados:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        
        ttk.Label(frame_display, textvariable=self.vol_live_counter_display_var, style="Counter.TLabel").pack(pady=5, anchor="center")
        
        # Botões de Ação (Linha 1)
        frame_buttons = ttk.Frame(frame_live_counter, padding=(10, 5))
        frame_buttons.grid(row=1, column=0, sticky="ew", padx=10, pady=5, columnspan=3)
        
        frame_buttons.columnconfigure((0, 1, 2), weight=1)
        
        btn_add_flow = ttk.Button(frame_buttons, text="➕ Adicionar 1 Fluxo", command=self.increment_live_counter)
        btn_add_flow.grid(row=0, column=0, sticky="ew", padx=(0, 5), ipady=12) 
        
        btn_remove_flow = ttk.Button(frame_buttons, text="➖ Remover 1 Fluxo", command=self.decrement_live_counter)
        btn_remove_flow.grid(row=0, column=1, sticky="ew", padx=5, ipady=12)

        btn_reset = ttk.Button(frame_buttons, text="🔄 Zerar Contador", command=self.reset_live_counter, style="Reset.TButton")
        btn_reset.grid(row=0, column=2, sticky="ew", padx=(5, 0), ipady=12)

        # Botão Transferir (Linha 2, expandido)
        btn_transfer = ttk.Button(frame_live_counter, text="Transferir Volume do Contador para o Registro Diário", command=self.use_live_counter_as_volume)
        btn_transfer.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(5, 0), ipady=8) 
        
        # Estilo temporário para o botão de reset (DANGER_RED)
        self.style.configure("Reset.TButton", font=("Segoe UI", 10, "bold"), padding=6, relief="flat", background=DANGER_RED, foreground="white")
        self.style.map("Reset.TButton", background=[("active", "#d00040")])

        # --- FIM: 0. CONTADOR DE FLUXO EM TEMPO REAL ---
        
        # 1. INPUT DE NOVO REGISTRO
        frame_vol_input = ttk.LabelFrame(frame_vol_main, text="Novo Registro Diário", style="TLabelframe")
        frame_vol_input.grid(row=1, column=0, sticky="ew", padx=5, pady=15) # Nova row 1
        frame_vol_input.columnconfigure(1, weight=1)

        # Campo 1: Data (Entry + Calendar Button)
        ttk.Label(frame_vol_input, text=f"Dia ({DATA_DISPLAY_CURTO}):", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        frame_data_input = ttk.Frame(frame_vol_input)
        frame_data_input.grid(row=0, column=1, sticky="ew", padx=10, pady=5, ipady=4)
        frame_data_input.columnconfigure(0, weight=1)
        
        entry_data = ttk.Entry(frame_data_input, textvariable=self.vol_data_var, style="Custom.TEntry")
        entry_data.grid(row=0, column=0, sticky="ew", ipady=4)
        entry_data.bind("<KeyRelease>", lambda e: self._apply_date_masking(e, 'short')) 
        
        # MODIFICADO: O botão do calendário agora chama a função simplificada open_date_selection_calendar
        btn_calendar = ttk.Button(
            frame_data_input, 
            text="📅", 
            width=5,
            command=lambda: self.open_date_selection_calendar(self, self.vol_data_var, entry_data) 
        )
        btn_calendar.grid(row=0, column=1, sticky="e", padx=(5,0))
        
        # Campo 2: Volume e Botão de Ação
        ttk.Label(frame_vol_input, text="Volume (Nº):").grid(row=0, column=2, sticky="w", padx=10, pady=5)
        ttk.Entry(frame_vol_input, textvariable=self.vol_volume_var, width=10, style="Custom.TEntry").grid(row=0, column=3, sticky="w", padx=10, pady=5, ipady=4)

        btn_registrar_dia = ttk.Button(frame_vol_input, text="Registrar", command=self.registrar_dia)
        btn_registrar_dia.grid(row=0, column=4, sticky="ns", padx=10, pady=5, ipady=4)

        # Campo 3: Notas/Problemas
        ttk.Label(frame_vol_input, text="Notas/Observações:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        ttk.Entry(frame_vol_input, textvariable=self.vol_notas_var, style="Custom.TEntry").grid(row=1, column=1, columnspan=4, sticky="ew", padx=10, pady=5, ipady=4)

        
        # 2. PERFORMANCE E FEEDBACK
        frame_performance = ttk.LabelFrame(frame_vol_main, text="Status do Mês: Seu Caminho para a Premiação", style="TLabelframe")
        frame_performance.grid(row=2, column=0, sticky="ew", padx=5, pady=10) # Nova row 2
        frame_performance.columnconfigure((0, 1, 2, 3), weight=1) 
        
        # Cartão 1: Total Mês
        ttk.Label(frame_performance, text="Total Acumulado", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="n", pady=(5, 0), padx=5)
        ttk.Label(frame_performance, textvariable=self.vol_total_var, style="Meta.TLabel", justify=tk.CENTER).grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 10))
        
        # Cartão 2: Meta Ativa (Mensal PREMIUM Calculada)
        ttk.Label(frame_performance, text="Alvo PREMIUM", font=("Segoe UI", 10)).grid(row=0, column=1, sticky="n", pady=(5, 0), padx=5)
        ttk.Label(frame_performance, textvariable=self.vol_meta_mensal_display_var, style="Meta.TLabel", justify=tk.CENTER).grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 10))
        
        # Cartão 3: Faltante
        ttk.Label(frame_performance, text="Faltante", font=("Segoe UI", 10)).grid(row=0, column=2, sticky="n", pady=(5, 0), padx=5)
        ttk.Label(frame_performance, textvariable=self.vol_faltante_var, style="Faltante.TLabel", justify=tk.CENTER).grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 10))
        
        # Cartão 4: Média Necessária
        ttk.Label(frame_performance, text="Média Diária Necessária", font=("Segoe UI", 10)).grid(row=0, column=3, sticky="n", pady=(5, 0), padx=5)
        ttk.Label(frame_performance, textvariable=self.vol_media_diaria_var, style="Media.TLabel", justify=tk.CENTER).grid(row=1, column=3, sticky="ew", padx=5, pady=(0, 10))
        
        # Linha de Feedback Motivacional
        ttk.Separator(frame_performance, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=4, sticky="ew", pady=5)
        ttk.Label(frame_performance, textvariable=self.vol_meta_feedback_var, style="Feedback.TLabel", wraplength=700).grid(row=3, column=0, columnspan=4, sticky="n", pady=(10, 5))
        
        
        # 3. HISTÓRICO DE REGISTROS
        frame_vol_hist = ttk.LabelFrame(frame_vol_main, text="Histórico de Registros (Mês Atual)", style="TLabelframe")
        # Colocado na row 3
        frame_vol_hist.grid(row=3, column=0, sticky="nsew", padx=5, pady=10) 
        # Esta linha NÃO deve se expandir no frame_vol_main, mas o treeview DENTRO dela SIM.
        frame_vol_hist.rowconfigure(0, weight=1) 
        frame_vol_hist.columnconfigure(0, weight=1)

        cols = ("Data", "Volume", "Notas")
        self.tree_vol = ttk.Treeview(frame_vol_hist, columns=cols, show="headings", style="Treeview")
        self.tree_vol.heading("Data", text="DATA")
        self.tree_vol.heading("Volume", text="VOLUME")
        self.tree_vol.heading("Notas", text="NOTAS")
        self.tree_vol.column("Data", width=100, anchor="w")
        self.tree_vol.column("Volume", width=80, anchor="center")
        self.tree_vol.column("Notas", width=400, anchor="w")

        scrollbar_vol = ttk.Scrollbar(frame_vol_hist, orient="vertical", command=self.tree_vol.yview)
        self.tree_vol.configure(yscrollcommand=scrollbar_vol.set)
        scrollbar_vol.grid(row=0, column=1, sticky="ns")
        self.tree_vol.grid(row=0, column=0, sticky="nsew")

        btn_remover_dia = ttk.Button(frame_vol_hist, text="Remover Dia Selecionado", command=self.remover_dia_selecionado)
        btn_remover_dia.grid(row=1, column=0, sticky="w", padx=5, pady=10)

    def salvar_volumetria_data(self):
        self.salvar_json(ARQUIVO_VOLUMETRIA, {"registros": self.volumetria_data})
        
    def get_dias_uteis_restantes(self):
        """Calcula o número de dias úteis (Seg-Sex) restantes no mês, incluindo hoje."""
        hoje = date.today()
        dia_atual = hoje.day
        _, total_dias_mes = calendar.monthrange(hoje.year, hoje.month)
        dias_restantes = 0
        
        for dia in range(dia_atual, total_dias_mes + 1):
            if date(hoje.year, hoje.month, dia).weekday() < 5: 
                dias_restantes += 1
        return dias_restantes

    def _parse_volumetria_date(self, date_string):
        """Tenta analisar a string de data usando múltiplos formatos de persistência."""
        formats_to_try = [DATA_FORMATO_LONGO_PERSIST, DATA_FORMATO_LONGO_ANTIGO]
        for fmt in formats_to_try:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        return None

    def atualizar_treeview_volumetria(self):
        """
        Limpa e recarrega o treeview com os dados e calcula os totais.
        [MODIFICADO] Lógica simplificada para usar Meta PRO (Mínimo) e Meta PREMIUM (Máximo/Ativa)
        e mensagens mais motivacionais.
        """
        if not self._gui_ready or not hasattr(self, 'tree_vol'): return
            
        for i in self.tree_vol.get_children():
            self.tree_vol.delete(i)
        
        mes_atual_id = date.today().strftime('%m-%Y') 
        total_mes = 0
        
        # 1. Carrega o config novamente para garantir as metas mais atualizadas
        config_data = self.carregar_json(ARQUIVO_CONFIG, self.carregar_config_padrao)
        
        # Obtém a Meta PRO Mensal e a Meta PREMIUM Mensal (ambas calculadas)
        try:
             meta_pro_mensal = config_data.get("meta_pro_mensal", 4000)
             meta_premium_mensal = config_data.get("meta_premium_mensal", 4500)
        except ValueError:
            meta_pro_mensal = 4000
            meta_premium_mensal = 4500
        
        # A meta ativa principal é sempre a PREMIUM calculada
        meta_maxima_ativa = meta_premium_mensal 
        self.meta_mensal = meta_maxima_ativa 
        
        feedback_text = ""
        feedback_style = "Motivacao.TLabel"
        
        # --- OBTENÇÃO DOS DADOS E CALCULO DO TOTAL_MES (Sempre necessário) ---
        data_with_objects = []
        for item in self.volumetria_data:
            date_obj = self._parse_volumetria_date(item.get('data', ''))
            if date_obj:
                data_with_objects.append({'data_obj': date_obj, **item})
                
        data_sorted = sorted(data_with_objects, key=lambda x: x['data_obj'], reverse=True)
                
        for item in data_sorted:
            date_obj = item['data_obj']
            display_date = date_obj.strftime(DATA_FORMATO_CURTO)
            
            # Recarrega o treeview
            self.tree_vol.insert("", tk.END, values=(display_date, item.get('volume', ''), item.get('notas', '')))
            
            if date_obj.strftime('%m-%Y') == mes_atual_id:
                try:
                    total_mes += int(item.get('volume', '0'))
                except ValueError:
                    pass
        
        # --- FIM: OBTENÇÃO DOS DADOS E CALCULO DO TOTAL_MES ---

        # Verificação do status de meta batida anterior
        meta_anterior_batida = self.meta_batida_mes.get() == mes_atual_id
        
        # CORREÇÃO CRÍTICA: Se a meta estava batida E a nova meta (meta_maxima_ativa) é maior que o total acumulado,
        # limpamos o estado de meta batida e forçamos o recalculo do feedback abaixo.
        if meta_anterior_batida and total_mes < meta_maxima_ativa:
            # Se a nova meta é maior que o total, a meta não está mais batida
            self.meta_batida_mes.set("")
            self.meta_batida_feedback.set("")
            # A flag será False para entrar no bloco de recalculo
            meta_anterior_batida = False
            # Salvamos a config para persistir a limpeza da flag
            self.salvar_config() 
        
        # Se a meta estava batida E o total é MAIOR ou IGUAL à nova meta, mantemos o feedback
        if meta_anterior_batida:
            feedback_text = self.meta_batida_feedback.get()
            feedback_style = "Parabens.TLabel"
            self.vol_faltante_var.set("0")
            self.vol_media_diaria_var.set("Meta Atingida!")
        else:
            # Bloco de Recalculo (Executado se a meta não foi batida OU se a meta foi aumentada)
            
            dias_restantes = self.get_dias_uteis_restantes()
            # Usa o meta_maxima_ativa (PREMIUM)
            faltante = max(0, meta_maxima_ativa - total_mes) 

            meta_batida = False
            user_name = self._get_first_name()
            name_part = user_name if user_name else 'parceiro(a)'

            # Verifica o status atual em relação às novas metas
            if total_mes >= meta_maxima_ativa:
                # Mensagem de premiação e qualidade
                feedback_text = f"🚀 META PREMIUM ({meta_maxima_ativa}) ATINGIDA! VOCÊ CONQUISTOU A PREMIAÇÃO! Parabéns, {name_part}, pela excelência e qualidade do seu trabalho. Resultado excepcional!"
                feedback_style = "Parabens.TLabel"
                meta_batida = True
            # Verifica se atingiu a meta PRO (se a meta PRO for menor que a PREMIUM)
            elif meta_pro_mensal < meta_maxima_ativa and total_mes >= meta_pro_mensal:
                feedback_text = f"✅ META PRO ({meta_pro_mensal}) BATIDA! Que ótimo, {name_part}! Seu volume já garante a qualidade. Agora, o foco total é na Meta PREMIUM ({meta_maxima_ativa}) para a premiação! Você consegue!"
                feedback_style = "Parabens.TLabel"
                # A Meta PRO não é considerada "Meta Batida" para fins de persistência/travamento de feedback,
                # apenas a PREMIUM.
            elif dias_restantes == 0:
                feedback_text = f"Mês encerrado. Total: {total_mes}. Não desanime! Foque na qualidade hoje e planeje como alcançar a Meta PREMIUM no próximo mês, {name_part}!"
                feedback_style = "Motivacao.TLabel"
            else:
                # Texto de motivação atualizado
                feedback_text = f"Faltam {faltante} fluxos para o seu Alvo PREMIUM ({meta_maxima_ativa}). Mantenha a qualidade em primeiro lugar e acelere nos próximos {dias_restantes} dias úteis, {name_part}! A premiação está ao seu alcance!"
                feedback_style = "Motivacao.TLabel"

            if meta_batida:
                self.meta_batida_mes.set(mes_atual_id)
                self.meta_batida_feedback.set(feedback_text)
                # Salvamos a config para persistir a nova flag de meta batida
                self.salvar_config() 

            if faltante == 0:
                media_diaria_display = "Meta Atingida!"
            elif dias_restantes == 0:
                media_diaria_display = "Mês encerrado"
            else:
                media_diaria = faltante / dias_restantes
                media_diaria_display = f"{media_diaria:.2f} / dia"

            self.vol_faltante_var.set(f"{faltante}")
            self.vol_media_diaria_var.set(media_diaria_display)
        
        
        self.style.configure("Feedback.TLabel", foreground=self.style.lookup(feedback_style, 'foreground'))
        self.vol_meta_feedback_var.set(feedback_text)
        self.vol_total_var.set(f"{total_mes}") 
        self.vol_meta_mensal_display_var.set(f"{meta_maxima_ativa}") # Exibe a meta ativa (PREMIUM calculada)

    def registrar_dia(self):
        """Adiciona um novo registro de volumetria com validação."""
        try:
            data_curta_str = self.vol_data_var.get().strip()
            volume_str = self.vol_volume_var.get().strip()
            notas_str = self.vol_notas_var.get()
            
            if not self._validate_date_format(data_curta_str, is_long_format=False):
                raise ValueError(f"A Data é obrigatória e precisa estar no formato {DATA_DISPLAY_CURTO}.")

            if not volume_str:
                 raise ValueError("O Volume é obrigatório. Queremos registrar seu esforço!")
                 
            try:
                volume_int = int(volume_str)
                if volume_int < 0:
                    raise ValueError("O Volume deve ser um número inteiro positivo. Se foi negativo, ajuste as notas!")
            except ValueError:
                 raise ValueError("O Volume deve ser um número inteiro. Sem vírgulas aqui.")
            
            data_full_obj = self._parse_full_date(data_curta_str, DATA_FORMATO_CURTO)
            data_full_str = data_full_obj.strftime(DATA_FORMATO_LONGO_PERSIST)
             
            registro_existente = any(d['data'] == data_full_str for d in self.volumetria_data)
            
            if registro_existente:
                if not messagebox.askyesno("Confirmar", f"O registro do dia {data_curta_str} já existe. Quer substituí-lo pelos novos dados?"):
                    return
                self.volumetria_data[:] = [d for d in self.volumetria_data if d['data'] != data_full_str]
                
            self.volumetria_data.append({"data": data_full_str, "volume": volume_str, "notas": notas_str})
            self.salvar_volumetria_data() 
            self.atualizar_treeview_volumetria()
            
            self.vol_data_var.set(date.today().strftime(DATA_FORMATO_CURTO))
            self.vol_volume_var.set("")
            self.vol_notas_var.set("")
            
            # Reset do contador ao registrar, pois o volume foi consolidado.
            self.reset_live_counter()
            
            first_name = self._get_first_name()
            self.atualizar_status(f"Registro de volume do dia {data_curta_str} salvo com sucesso! Ótimo trabalho, {first_name}!")
            
        except ValueError as ve: 
            self.atualizar_status(f"Ops! {ve}")
        except Exception as e: 
            self.atualizar_status(f"Erro ao registrar: {e}")

    def remover_dia_selecionado(self):
        """Remove o dia selecionado do Treeview e dos dados."""
        try:
            selected_item = self.tree_vol.selection()[0]
            values = self.tree_vol.item(selected_item, 'values')
            data_curta_str = values[0]
            
            date_full_obj = self._parse_full_date(data_curta_str, DATA_FORMATO_CURTO)
            data_full_str = date_full_obj.strftime(DATA_FORMATO_LONGO_PERSIST)
            
            first_name = self._get_first_name()

            if not messagebox.askyesno("Confirmar", f"Tem certeza que deseja remover o registro de {data_curta_str}? Isso apagará seu volume da contagem mensal."):
                return
                
            self.volumetria_data[:] = [d for d in self.volumetria_data if d['data'] != data_full_str]
            self.salvar_volumetria_data() 
            self.atualizar_treeview_volumetria()
            self.atualizar_status(f"Registro de {data_curta_str} removido. {first_name}, vamos nos manter atualizados!")
        except IndexError:
            self.atualizar_status("Selecione um dia da lista para poder removê-lo.")
        except Exception as e:
            self.atualizar_status(f"Erro ao remover: {e}")
            
    # --- Aba 4.5: Anotações Gerais (NOVA ABA) ---
    def _save_anotacoes_file(self):
        """Salva o conteúdo da StringVar de anotações no arquivo JSON dedicado."""
        data = {"anotacoes": self.anotacoes_gerais_var.get()}
        self.salvar_json(ARQUIVO_ANOTACOES, data)
        
    def _update_anotacoes_content(self, event=None, save_to_var=True):
        """Atualiza a StringVar de anotações e salva no arquivo se for FocusOut."""
        if not hasattr(self, 'anotacoes_text'): return
        
        if save_to_var:
             # Atualiza a variável com o conteúdo do widget
            content = self.anotacoes_text.get('1.0', tk.END).strip()
            self.anotacoes_gerais_var.set(content)
            
            # Salva no arquivo (FocusOut ou outra chamada explícita)
            if event and event.type == '9': # '9' é FocusOut
                self._save_anotacoes_file()
                first_name = self._get_first_name()
                self.atualizar_status(f"Anotações salvas automaticamente! Mente organizada, {first_name}!")
        else:
            # Recarrega o widget com o conteúdo da variável (ao trocar de aba)
            # Nota: O conteúdo com tags NÃO é lido/salvo diretamente, mas apenas o texto. 
            # A formatação é temporária na sessão.
            self.anotacoes_text.delete('1.0', tk.END)
            self.anotacoes_text.insert(tk.END, self.anotacoes_gerais_var.get())
            
    def _toggle_formatting(self, tag_name):
        """Aplica ou remove uma tag de formatação (negrito/italico) no texto selecionado."""
        try:
            # Pega o ScrolledText ativo
            text_widget = self.anotacoes_text
            
            # Pega o início e o fim da seleção
            start = text_widget.tag_ranges(tk.SEL)[0]
            end = text_widget.tag_ranges(tk.SEL)[1]
            
            # Verifica se a tag já está aplicada em *alguma parte* da seleção
            tag_is_active = any(tag_name in text_widget.tag_names(idx) 
                                for idx in text_widget.tag_ranges(tag_name)
                                if idx >= start and idx < end)
            
            if tag_is_active:
                # Se estiver ativa, remove a tag de toda a seleção
                text_widget.tag_remove(tag_name, start, end)
            else:
                # Se não estiver, aplica a tag
                text_widget.tag_add(tag_name, start, end)
                
            # Força o foco para que o KeyRelease possa salvar (se necessário)
            text_widget.focus_set()
            
            self.atualizar_status(f"Formatação '{tag_name.capitalize()}' aplicada.")

        except tk.TclError:
            self.atualizar_status("Selecione o texto que você quer destacar!")
        except Exception as e:
            self.atualizar_status(f"Erro ao aplicar formatação: {e}")
            
    def _toggle_align(self, align_type):
        """Altera o alinhamento do texto selecionado."""
        try:
            text_widget = self.anotacoes_text
            
            # Pega o índice da linha inicial e final da seleção
            start_line = text_widget.index(tk.SEL_FIRST).split('.')[0]
            end_line = text_widget.index(tk.SEL_LAST).split('.')[0]
            
            # Remove todas as tags de alinhamento existentes na seleção
            for tag in ['align_left', 'align_center', 'align_right']:
                 # Remove por linha, para evitar conflito com formatação inline
                 text_widget.tag_remove(tag, f"{start_line}.0", f"{int(end_line)+1}.0")

            # Aplica a nova tag de alinhamento (apenas se não for o padrão 'align_left')
            if align_type != 'align_left': 
                text_widget.tag_add(align_type, f"{start_line}.0", f"{int(end_line)+1}.0")
            
            text_widget.focus_set()
            self.atualizar_status(f"Alinhamento '{align_type.split('_')[-1].capitalize()}' aplicado.")

        except tk.TclError:
            self.atualizar_status("Selecione o texto para ajustar o alinhamento.")
        except Exception as e:
            self.atualizar_status(f"Erro ao aplicar alinhamento: {e}")


    def criar_aba_anotacoes(self):
        """Cria os widgets da nova Aba de Anotações."""
        tab_anotacoes = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(tab_anotacoes, text="Anotações")
        
        tab_anotacoes.columnconfigure(0, weight=1)
        tab_anotacoes.rowconfigure(1, weight=1) # Row do ScrolledText

        # --- Frame Principal (para manter o layout) ---
        frame_anotacoes_main = ttk.Frame(tab_anotacoes)
        frame_anotacoes_main.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frame_anotacoes_main.columnconfigure(0, weight=1)
        frame_anotacoes_main.rowconfigure(1, weight=1) 
        
        # --- Toolbar Container (Row 0) ---
        frame_toolbar_container = ttk.Frame(frame_anotacoes_main, style="TFrame")
        frame_toolbar_container.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 5))
        
        # Faz o container interno se expandir e centraliza o botão container
        frame_toolbar_container.columnconfigure(0, weight=1)
        
        # Frame de Botões (Onde o agrupamento e o centralizar de fato acontece)
        button_container = ttk.Frame(frame_toolbar_container, style="TFrame")
        # Centraliza o container de botões dentro do frame_toolbar_container
        button_container.grid(row=0, column=0, sticky="") 
        
        # --- Grupo 1: Formatação ---
        btn_bold = ttk.Button(button_container, text="𝗕", command=lambda: self._toggle_formatting('negrito'), width=3, style="Toolbar.TButton")
        btn_bold.pack(side=tk.LEFT, padx=(0, 3))
        
        btn_italic = ttk.Button(button_container, text="𝐼", command=lambda: self._toggle_formatting('italico'), width=3, style="Toolbar.TButton")
        btn_italic.pack(side=tk.LEFT, padx=(0, 10))

        # --- Separador 1 ---
        ttk.Separator(button_container, orient=tk.VERTICAL, style="TVSeparator.TSeparator").pack(side=tk.LEFT, padx=5, fill='y')
        
        # --- Grupo 2: Alinhamento ---
        # Removida a palavra "Align" para deixar os botões menores e mais limpos
        btn_align_left = ttk.Button(button_container, text="⬅️", command=lambda: self._toggle_align('align_left'), width=3, style="Toolbar.TButton")
        btn_align_left.pack(side=tk.LEFT, padx=3)

        btn_align_center = ttk.Button(button_container, text="C", command=lambda: self._toggle_align('align_center'), width=3, style="Toolbar.TButton")
        btn_align_center.pack(side=tk.LEFT, padx=3)

        btn_align_right = ttk.Button(button_container, text="➡️", command=lambda: self._toggle_align('align_right'), width=3, style="Toolbar.TButton")
        btn_align_right.pack(side=tk.LEFT, padx=(3, 10))

        # --- Separador 2 ---
        ttk.Separator(button_container, orient=tk.VERTICAL, style="TVSeparator.TSeparator").pack(side=tk.LEFT, padx=5, fill='y')

        # --- Grupo 3: Edição ---
        btn_undo = ttk.Button(button_container, text="↩️", command=lambda: self.anotacoes_text.edit_undo(), width=3, style="Toolbar.TButton")
        btn_undo.pack(side=tk.LEFT, padx=3)
        
        btn_redo = ttk.Button(button_container, text="↪️", command=lambda: self.anotacoes_text.edit_redo(), width=3, style="Toolbar.TButton")
        btn_redo.pack(side=tk.LEFT, padx=(3, 10))

        # --- Separador 3 ---
        ttk.Separator(button_container, orient=tk.VERTICAL, style="TVSeparator.TSeparator").pack(side=tk.LEFT, padx=5, fill='y')
        
        # --- Grupo 4: Limpeza ---
        btn_clear_tags = ttk.Button(button_container, text="🗑️ Limpar Formatação", command=lambda: self.anotacoes_text.tag_remove(tk.ALL, '1.0', tk.END), style="Toolbar.TButton")
        btn_clear_tags.pack(side=tk.LEFT, padx=3)
        
        # --- ScrolledText (Row 1) ---
        self.anotacoes_text = scrolledtext.ScrolledText(
            frame_anotacoes_main, 
            wrap=tk.WORD, 
            font=("Segoe UI", 10), 
            relief="flat", 
            borderwidth=1, 
            highlightbackground="#DDDDDD", 
            bg="#FFFFFF",
            padx=10, 
            pady=10,
            undo=True # Habilita o rastreamento de histórico para Undo/Redo
        )
        self.anotacoes_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # --- Definição das Tags (Styles) ---
        default_font = tkFont.Font(font=self.anotacoes_text.cget("font"))
        
        # Formatação
        bold_font = tkFont.Font(font=default_font.copy())
        bold_font.configure(weight="bold")
        self.anotacoes_text.tag_configure('negrito', font=bold_font)
        
        italic_font = tkFont.Font(font=default_font.copy())
        italic_font.configure(slant="italic")
        self.anotacoes_text.tag_configure('italico', font=italic_font)

        # Alinhamento
        self.anotacoes_text.tag_configure('align_center', justify=tk.CENTER)
        self.anotacoes_text.tag_configure('align_right', justify=tk.RIGHT)
        self.anotacoes_text.tag_configure('align_left', justify=tk.LEFT) 

        # Carrega o conteúdo inicial da variável salva
        self.anotacoes_text.insert(tk.END, self.anotacoes_gerais_var.get())

        # Bind para salvar automaticamente ao digitar e perder o foco
        self.anotacoes_text.bind("<KeyRelease>", self._update_anotacoes_content)
        self.anotacoes_text.bind("<FocusOut>", self._update_anotacoes_content)

        # Rótulo de rodapé da aba (fora do frame_anotacoes_main para ficar no final da aba)
        ttk.Label(tab_anotacoes, text="Anotações são salvas automaticamente ao digitar ou mudar de aba.", 
                  font=("Segoe UI", 9, "italic"), foreground="gray").grid(row=1, column=0, sticky="sw", padx=10, pady=5)
    
    # --- Aba 5: Agendas ---
    
    def criar_aba_agendas(self):
        """Cria todos os widgets da Aba 6: Agendas, agora incluindo a Daily no Treeview."""
        # Se já estiver inicializada, apenas atualiza e retorna
        if hasattr(self, '_agendas_initialized') and self._agendas_initialized:
            self.atualizar_lista_agendas()
            return

        tab_agendas = self.aba_agendas_frame
        
        # Limpa o frame da aba
        for widget in tab_agendas.winfo_children():
            widget.destroy()

        frame_agenda_main = ttk.Frame(tab_agendas)
        frame_agenda_main.pack(fill="both", expand=True, pady=5)
        frame_agenda_main.columnconfigure(0, weight=1)
        frame_agenda_main.rowconfigure(1, weight=1) # Faz o Treeview expandir
        
        # 1. Mensagem de Ajuda sobre Daily
        daily_msg = "Seu alinhamento diário e compromissos importantes. Lembre-se, o horário da Daily é configurado em Menu > Configuração."
        
        ttk.Label(frame_agenda_main, text=daily_msg, font=("Segoe UI", 9, "italic"), foreground="gray", wraplength=700).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        # 2. COMPROMISSOS AGENDADOS (Treeview)
        frame_tabela_agenda = ttk.LabelFrame(frame_agenda_main, text="Compromissos Agendados", style="TLabelframe")
        frame_tabela_agenda.grid(row=1, column=0, sticky="nsew", padx=5, pady=5) 
        frame_tabela_agenda.rowconfigure(0, weight=1)
        frame_tabela_agenda.columnconfigure(0, weight=1)
        
        # Adicionado o Tipo de volta para diferenciar Daily e Única
        cols = ("Tipo", "Data", "Hora", "Descrição") 
        self.tree_agendas = ttk.Treeview(frame_tabela_agenda, columns=cols, show="headings", style="Treeview")
        
        self.tree_agendas.heading("Tipo", text="TIPO", anchor="center")
        self.tree_agendas.heading("Data", text="DATA", anchor="center")
        self.tree_agendas.heading("Hora", text="HORA", anchor="center")
        self.tree_agendas.heading("Descrição", text="DESCRIÇÃO") 
        
        self.tree_agendas.column("Tipo", width=120, anchor="w", stretch=tk.NO) # Aumentado o espaço
        self.tree_agendas.column("Data", width=100, anchor="center", stretch=tk.NO)
        self.tree_agendas.column("Hora", width=70, anchor="center", stretch=tk.NO)
        self.tree_agendas.column("Descrição", width=400, anchor="w", stretch=tk.YES)
        
        self.tree_agendas.tag_configure('daily_wday', background='#FFF5E6', foreground='#A0522D')
        self.tree_agendas.tag_configure('single', background='#E6F5FF', foreground='#004494')
        self.tree_agendas.tag_configure('custom_wday', background='#F0EFFF', foreground='#6A0DAD')
        
        self.tree_agendas.bind("<Double-1>", lambda e: self.abrir_agenda_link())
        
        scrollbar_agenda = ttk.Scrollbar(frame_tabela_agenda, orient="vertical", command=self.tree_agendas.yview)
        self.tree_agendas.configure(yscrollcommand=scrollbar_agenda.set)
        
        scrollbar_agenda.grid(row=0, column=1, sticky="ns")
        self.tree_agendas.grid(row=0, column=0, sticky="nsew")

        # 3. Botões de Ação
        frame_btn_agenda = ttk.Frame(frame_agenda_main)
        frame_btn_agenda.grid(row=2, column=0, sticky="ew", padx=5, pady=(15, 0))
        
        # RENOMEADO: Adicionar Agenda Única -> Adicionar Compromisso
        btn_add = ttk.Button(frame_btn_agenda, text="➕ Adicionar Compromisso", command=self.adicionar_agenda)
        # RENOMEADO: Editar Agenda Única -> Editar Compromisso
        btn_edit = ttk.Button(frame_btn_agenda, text="✏️ Editar Compromisso", command=lambda: self.adicionar_agenda(is_edit=True))
        # RENOMEADO: Remover Agenda Única -> Remover Compromisso
        btn_remove = ttk.Button(frame_btn_agenda, text="❌ Remover Compromisso Único/Recorrente", command=self.remover_agenda)
        
        btn_add.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 5))
        btn_edit.pack(side=tk.LEFT, fill="x", expand=True, padx=5)
        btn_remove.pack(side=tk.LEFT, fill="x", expand=True, padx=(5, 0))

        ttk.Separator(frame_agenda_main, orient=tk.HORIZONTAL).grid(row=3, column=0, sticky="ew", pady=(20, 0))
        
        self._agendas_initialized = True
        self.atualizar_lista_agendas()
        
    # REMOVIDO: A função _create_daily_panel foi removida conforme solicitação.
    # def _create_daily_panel(self, parent): ...

    # REMOVIDO: A função _clear_daily_time foi removida, pois o input da daily foi movido.
    # def _clear_daily_time(self): ...

    def atualizar_lista_agendas(self):
        """Limpa e recarrega o treeview, incluindo a Daily (se configurada) e recorrências customizadas."""
        if not hasattr(self, 'tree_agendas'):
            return
            
        for i in self.tree_agendas.get_children():
            self.tree_agendas.delete(i)
        
        daily_time = self.daily_time_var.get().strip()
        daily_team_name = self.team_var.get().strip()
        
        # Mapeamento de índices de dias da semana (Python: 0=Seg, 6=Dom) para Nomes
        WEEKDAYS_MAP = {
            0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 
            4: "Sex", 5: "Sáb", 6: "Dom"
        }
        
        # 1. Insere a Daily Recorrente padrão (Seg-Sex) se configurada
        if self._validate_time_format(daily_time):
            daily_desc = f"Sua Daily - Time {daily_team_name if daily_team_name else 'sem nome'}"
            # iid="-1" para ser facilmente identificável como item não editável
            self.tree_agendas.insert("", tk.END, iid="-1", 
                                     values=("Diário Padrão", "Seg-Sex", daily_time, daily_desc), 
                                     tags=('daily_wday',))
        
        # 2. Insere as Agendas Únicas e Recorrentes (ordenadas)
        agendas_to_display = sorted(self.agendas_data, 
            key=lambda x: (
                x.get('repeticao') != 'single', # Coloca 'single' (False) primeiro
                datetime.strptime(x.get('data', '01/01/9999'), DATA_FORMATO_LONGO_PERSIST) if x.get('repeticao') == 'single' else datetime.max,
                x.get('hora', '99:99')
            )
        )
            
        # Reestrutura self.agendas_data para conter apenas agendas únicas e recorrentes personalizadas
        self.agendas_data[:] = [item for item in agendas_to_display if item.get('repeticao') != 'daily_wday']

        for i, item in enumerate(self.agendas_data):
            
            repeticao = item.get('repeticao', 'single')
            
            if repeticao == 'single':
                try:
                    date_obj = datetime.strptime(item.get('data', '01/01/9999'), DATA_FORMATO_LONGO_PERSIST)
                    data_display = date_obj.strftime(DATA_FORMATO_CURTO)
                except ValueError:
                    data_display = "Erro Data"
                tipo_display = "Única Data"
                tags = ('single',)
            
            elif repeticao == 'daily_wday_custom':
                # Dias da semana são salvos como string de lista de índices [0, 1, 2,...]
                dias_list = []
                try:
                    dias_indices = ast.literal_eval(item.get('dias_semana', '[]'))
                    dias_list = [WEEKDAYS_MAP.get(d, 'Inv') for d in dias_indices]
                except Exception:
                    dias_list = ["Erro Dia"]
                
                data_display = ", ".join(dias_list)
                tipo_display = "Recorrente Semanal"
                tags = ('custom_wday',)
            else:
                 continue # Ignora repetições inválidas ou Daily Padrão (já tratada acima)

            # Usando iid como índice da lista agendas_data para edição/remoção
            iid_val = str(i)
            
            values = (tipo_display, data_display, item.get('hora', 'N/A'), item.get('descricao', 'N/A'))
            
            self.tree_agendas.insert("", tk.END, iid=iid_val, values=values, tags=tags)
            
    # CORREÇÃO: A função open_date_selection_calendar estava duplicada, removi a duplicata.

    def _get_agenda_input_window(self, master, initial_data=None):
        """
        Cria e exibe a janela customizada para adicionar/editar agendas,
        agora com opção de recorrência semanal.
        """
        
        is_edit = bool(initial_data)
        
        # Valores Iniciais
        today_short_str = date.today().strftime(DATA_FORMATO_CURTO)
        
        repeticao_default = initial_data.get('repeticao', 'single') if is_edit else 'single'
        data_default = initial_data.get('data_display', today_short_str) if is_edit and repeticao_default == 'single' else today_short_str
        dias_semana_default = ast.literal_eval(initial_data.get('dias_semana', '[]')) if is_edit and repeticao_default == 'daily_wday_custom' else []
            
        hora_default = initial_data.get('hora', '09:00') if is_edit else '09:00'
        desc_default = initial_data.get('descricao', '') if is_edit else ''
        link_default = initial_data.get('link', '') if is_edit else ''

        dialog = tk.Toplevel(master)
        dialog.title(("Editar" if is_edit else "Adicionar") + " Compromisso")
        dialog.transient(master)
        dialog.grab_set() 
        dialog.resizable(False, False)
        
        result_data = {}
        
        # Variáveis de Estado
        v_tipo_agenda = tk.StringVar(value=repeticao_default)
        v_data = tk.StringVar(value=data_default)
        v_hora = tk.StringVar(value=hora_default)
        v_descricao = tk.StringVar(value=desc_default)
        v_link = tk.StringVar(value=link_default)
        
        # Variáveis dos Dias da Semana (0=Seg, ..., 6=Dom)
        v_dias = [tk.BooleanVar() for _ in range(7)]
        for i in dias_semana_default:
            if 0 <= i <= 6:
                v_dias[i].set(True)

        
        # 1. Frame de Conteúdo Principal
        frame = ttk.Frame(dialog, padding="15", style="TFrame")
        frame.pack(fill="x", expand=True)
        
        frame_campos = ttk.Frame(frame)
        frame_campos.pack(fill="x")
        frame_campos.columnconfigure(1, weight=1)
        
        # --- Linha 1: Tipo de Agenda (Recorrência) ---
        ttk.Label(frame_campos, text="1. Tipo de Compromisso:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=5, padx=5)
        
        frame_radio_tipo = ttk.Frame(frame_campos)
        frame_radio_tipo.grid(row=0, column=1, sticky="w", pady=5, padx=5, columnspan=2)
        
        radio_single = ttk.Radiobutton(frame_radio_tipo, text="Única Data", variable=v_tipo_agenda, value="single", command=lambda: update_date_input())
        radio_custom = ttk.Radiobutton(frame_radio_tipo, text="Recorrente Semanal", variable=v_tipo_agenda, value="daily_wday_custom", command=lambda: update_date_input())
        radio_single.pack(side=tk.LEFT, padx=5)
        radio_custom.pack(side=tk.LEFT, padx=15)
        
        # --- Linha 2: Data (Container Condicional) ---
        ttk.Label(frame_campos, text="2. Data ou Dias:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=5, padx=5)
        
        # Container para Data Única
        frame_data_single = ttk.Frame(frame_campos)
        frame_data_single.grid(row=1, column=1, sticky="ew", pady=5, padx=5, columnspan=2)
        frame_data_single.columnconfigure(0, weight=1)
        
        entry_data = ttk.Entry(frame_data_single, textvariable=v_data, style="Custom.TEntry", width=15)
        entry_data.grid(row=0, column=0, sticky="ew", ipady=4)
        entry_data.bind("<KeyRelease>", lambda e: self._apply_date_masking(e, 'short'))
        
        btn_calendar = ttk.Button(
            frame_data_single, 
            text="📅", 
            width=5,
            command=lambda: self.open_date_selection_calendar(dialog, v_data, entry_data) 
        )
        btn_calendar.grid(row=0, column=1, sticky="e", padx=(5,0))
        
        # Container para Recorrência Semanal
        frame_dias_semana = ttk.Frame(frame_campos)
        frame_dias_semana.grid(row=1, column=1, sticky="ew", pady=5, padx=5, columnspan=2)
        
        dias_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        for i, label in enumerate(dias_labels):
            chk = ttk.Checkbutton(frame_dias_semana, text=label, variable=v_dias[i], style="Toolbutton")
            chk.pack(side=tk.LEFT, padx=2)
        
        def update_date_input():
            """Função para alternar a exibição dos campos de Data/Dias."""
            if v_tipo_agenda.get() == "single":
                frame_dias_semana.grid_forget()
                frame_data_single.grid(row=1, column=1, sticky="ew", pady=5, padx=5, columnspan=2)
            else:
                frame_data_single.grid_forget()
                frame_dias_semana.grid(row=1, column=1, sticky="ew", pady=5, padx=5, columnspan=2)

        # Inicializa a interface com o tipo correto
        update_date_input()

        # --- Linha 3: Hora ---
        ttk.Label(frame_campos, text=f"3. Hora ({HORA_DISPLAY}):", font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", pady=5, padx=5)
        entry_hora = ttk.Entry(frame_campos, textvariable=v_hora, style="Custom.TEntry", width=10)
        entry_hora.grid(row=2, column=1, sticky="w", pady=5, padx=5, ipady=4, columnspan=2)
        entry_hora.bind("<KeyRelease>", self._apply_time_masking)

        # --- Linha 4: Descrição ---
        ttk.Label(frame_campos, text="4. Descrição (Ex: Reunião de Alinhamento):", font=("Segoe UI", 10)).grid(row=3, column=0, sticky="w", pady=5, padx=5)
        ttk.Entry(frame_campos, textvariable=v_descricao, style="Custom.TEntry").grid(row=3, column=1, sticky="ew", pady=5, padx=5, ipady=4, columnspan=2)

        # --- Linha 5: Link (opcional) ---
        ttk.Label(frame_campos, text="5. Link da Reunião (opcional):", font=("Segoe UI", 10)).grid(row=4, column=0, sticky="w", pady=5, padx=5)
        ttk.Entry(frame_campos, textvariable=v_link, style="Custom.TEntry").grid(row=4, column=1, sticky="ew", pady=5, padx=5, ipady=4, columnspan=2)
        
        
        # 2. Frame de Botões 
        frame_buttons = ttk.Frame(dialog, padding=(15, 0)) 
        frame_buttons.pack(fill="x", pady=(0, 15)) 
        
        frame_buttons.columnconfigure(0, weight=1) 
        frame_buttons.columnconfigure(1, weight=1) 
        
        def on_ok():
            nonlocal result_data
            try:
                tipo = v_tipo_agenda.get()
                hora_str = v_hora.get().strip()
                descricao = v_descricao.get().strip()
                link = v_link.get().strip()
                
                if not descricao: raise ValueError("A Descrição é obrigatória. Precisamos saber sobre o que é o compromisso!")
                if not self._validate_time_format(hora_str): raise ValueError("O formato da Hora precisa ser HH:MM (ex: 09:30).")
                
                data_save_str = ""
                dias_semana_save = []
                
                if tipo == "single":
                    data_str = v_data.get().strip()
                    if not self._validate_date_format(data_str, is_long_format=False): 
                        raise ValueError(f"O formato da Data única precisa ser {DATA_DISPLAY_CURTO}.")
                    
                    date_full_obj = self._parse_full_date(data_str, DATA_FORMATO_CURTO)
                    data_save_str = date_full_obj.strftime(DATA_FORMATO_LONGO_PERSIST)
                
                elif tipo == "daily_wday_custom":
                    # Coleta os índices dos dias selecionados (0=Seg até 6=Dom)
                    dias_semana_save = [i for i, var in enumerate(v_dias) if var.get()]
                    if not dias_semana_save:
                         raise ValueError("Para um compromisso recorrente, selecione pelo menos um dia da semana.")
                
                # Monta o objeto de dados final
                result_data = {
                    "hora": hora_str,
                    "descricao": descricao,
                    "link": link,
                    "repeticao": tipo,
                }
                
                if tipo == "single":
                    result_data["data"] = data_save_str
                else: # daily_wday_custom
                    result_data["dias_semana"] = str(dias_semana_save) # Salva como string de lista
                    # Data é opcional para recorrência, mas é bom ter uma de referência (hoje)
                    result_data["data"] = date.today().strftime(DATA_FORMATO_LONGO_PERSIST) 

                dialog.destroy()
            except ValueError as ve:
                messagebox.showerror("Erro de Validação", str(ve))
            except Exception as e:
                messagebox.showerror("Erro Inesperado", f"Ocorreu um erro: {e}")

        btn_text = "Salvar Alterações" if is_edit else "Adicionar Compromisso"
        
        ttk.Button(frame_buttons, text=btn_text, command=on_ok).pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 5), ipady=8)
        ttk.Button(frame_buttons, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, fill="x", expand=True, padx=(5, 0), ipady=8)

        dialog.update_idletasks()
        w = dialog.winfo_reqwidth()
        h = dialog.winfo_reqheight()
        x = master.winfo_x() + (master.winfo_width() // 2) - (w // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (h // 2)
        dialog.geometry(f'{w}x{h}+{x}+{y}') 
        
        master.wait_window(dialog)
        return result_data

    def adicionar_agenda(self, is_edit=False):
        """Adiciona ou edita um compromisso (único ou recorrente)."""
        index_to_edit = -1
        initial_data = {}
        
        if is_edit:
            try:
                selected_item_iid = self.tree_agendas.selection()[0]
                
                # BLOQUEIO: Não permite editar a Daily Recorrente Padrão
                if selected_item_iid == "-1":
                    messagebox.showerror("Ação Bloqueada", "Para editar sua Daily Recorrente, vá em Menu > Configuração > Configurações Gerais.")
                    return
                     
                index_to_edit = int(selected_item_iid)
                initial_data = self.agendas_data[index_to_edit]
                
                # Prepara a data de exibição para compromisso único
                if initial_data.get('repeticao') == 'single':
                    date_obj = datetime.strptime(initial_data.get('data'), DATA_FORMATO_LONGO_PERSIST)
                    initial_data['data_display'] = date_obj.strftime(DATA_FORMATO_CURTO)
                
            except IndexError:
                self.atualizar_status("Selecione um compromisso na lista para poder editá-lo.")
                return
            except ValueError:
                 self.atualizar_status("Ops! Seleção inválida. Escolha um compromisso para editar.")
                 return


        new_data = self._get_agenda_input_window(self, initial_data)
        
        if not new_data: return 

        if is_edit:
            self.agendas_data[index_to_edit] = new_data
            self.atualizar_status("Compromisso editado com sucesso!")
        else:
            self.agendas_data.append(new_data)
            self.atualizar_status("Novo compromisso agendado! Preparado para o próximo passo.")
        
        self.salvar_json(ARQUIVO_AGENDAS, self.agendas_data) 
        self.atualizar_lista_agendas()
        
    def remover_agenda(self):
        """Remove o compromisso selecionado (apenas se for 'single' ou 'daily_wday_custom')."""
        try:
            selected_item_iid = self.tree_agendas.selection()[0]
            
            # BLOQUEIO: Não permite remover a Daily Recorrente Padrão
            if selected_item_iid == "-1":
                 messagebox.showerror("Ação Bloqueada", "Para remover sua Daily Recorrente Padrão, limpe a 'Hora da Daily' em Menu > Configuração > Configurações Gerais.")
                 return
                 
            index_to_remove = int(selected_item_iid)
            
            desc = self.agendas_data[index_to_remove].get('descricao', 'item')
            first_name = self._get_first_name()

            if messagebox.askyesno("Confirmar", f"Tem certeza que deseja remover o compromisso '{desc}'?"):
                self.agendas_data.pop(index_to_remove)
                self.salvar_json(ARQUIVO_AGENDAS, self.agendas_data)
                self.atualizar_lista_agendas()
                self.atualizar_status(f"Compromisso '{desc}' removido. Agenda ajustada, {first_name}!")
        except IndexError:
            self.atualizar_status("Por favor, selecione um compromisso para remover.")
        except Exception as e:
            self.atualizar_status(f"Erro ao remover: {e}")

    def abrir_agenda_link(self):
        """Abre o link da agenda selecionada."""
        try:
            selected_item_iid = self.tree_agendas.selection()[0]
            
            # BLOQUEIO: A Daily (iid="-1") não deve ter link aberto aqui, a menos que adicionemos o link ao config.
            if selected_item_iid == "-1":
                messagebox.showinfo("Informação", "Este é o seu compromisso de Daily e não tem um link direto cadastrado.")
                return
                
            index = int(selected_item_iid)
            link = self.agendas_data[index].get('link')
            
            if link:
                self.abrir_link_url(link)
            else:
                self.atualizar_status("Este compromisso não tem um link cadastrado. Você pode editá-lo para adicionar um!")
        except IndexError:
            self.atualizar_status("Selecione o compromisso cujo link você quer abrir.")
        except Exception as e:
            self.atualizar_status(f"Erro ao abrir link: {e}")

    # --- Funções de Lembrete (Thread) ---
    
    # OBS: iniciar_thread_atalhos está repetida aqui, mantive a primeira versão.

    def iniciar_thread_verificacao_agendas(self):
        """Inicia a thread para verificar as agendas."""
        self.thread_agendas = threading.Thread(target=self.check_agendas_thread, daemon=True)
        self.thread_agendas.start()

    def check_agendas_thread(self):
        """(Roda em Thread) Verifica as agendas a cada 60 segundos."""
        while self.app_rodando:
            self.check_for_reminders()
            time.sleep(60)

    def check_for_reminders(self):
        """
        [MODIFICADO] Verifica compromissos agendados, incluindo Daily Padrão,
        e recorrências por dia da semana.
        """
        now = datetime.now()
        is_weekday = (now.weekday() < 5) 
        today_weekday_index = now.weekday() # 0=Seg, 6=Dom
        
        # 1. Agendas a serem verificadas HOJE
        agendas_to_check = []
        
        # --- 1.1. Daily Padrão (Seg-Sex) ---
        daily_time = self.daily_time_var.get().strip()
        if self._validate_time_format(daily_time) and is_weekday:
            daily_datetime_today = datetime.combine(now.date(), datetime.strptime(daily_time, HORA_FORMATO).time())
            agendas_to_check.append({
                "data_time_obj": daily_datetime_today,
                "descricao": f"Sua Daily - Time {self.team_var.get().strip() if self.team_var.get().strip() else 'sem nome'}",
                "link": "",
                "repeticao": "daily_wday" 
            })
            
        # --- 1.2. Agendas Únicas e Recorrentes Customizadas ---
        for item in self.agendas_data:
            agenda_time = None
            repeticao = item.get('repeticao', 'single')
            
            if repeticao == 'single':
                try:
                    # Verifica se a data única é HOJE
                    data_hora_str = f"{item['data']} {item['hora']}"
                    agenda_time = datetime.strptime(data_hora_str, f"{DATA_FORMATO_LONGO_PERSIST} {HORA_FORMATO}")
                    if agenda_time.date() == now.date():
                        item['data_time_obj'] = agenda_time
                        agendas_to_check.append(item)
                except Exception:
                    continue # Ignora item com data inválida
            
            elif repeticao == 'daily_wday_custom':
                try:
                    # Verifica se o dia de hoje está na lista de recorrência
                    dias_indices = ast.literal_eval(item.get('dias_semana', '[]'))
                    if today_weekday_index in dias_indices:
                        hora_obj = datetime.strptime(item['hora'], HORA_FORMATO).time()
                        agenda_time = datetime.combine(now.date(), hora_obj)
                        item['data_time_obj'] = agenda_time
                        agendas_to_check.append(item)
                except Exception:
                    continue # Ignora item com dias_semana inválido

        # --- 2. Verifica lembretes para as agendas de HOJE ---
        for item in agendas_to_check:
            agenda_time = item['data_time_obj']
            
            if agenda_time > now:
                time_difference = agenda_time - now
                
                if (timedelta(minutes=9) <= time_difference <= timedelta(minutes=11)):
                    self.after(0, lambda d=item['descricao'], l=item['link']: self.show_agenda_reminder(d, l, 10))

                elif (timedelta(minutes=0) <= time_difference <= timedelta(minutes=2)):
                    self.after(0, lambda d=item['descricao'], l=item['link']: self.show_agenda_reminder(d, l, 1))
                
    def show_agenda_reminder(self, descricao, link, minutos_restantes):
        """Cria e exibe um popup de lembrete de reunião."""
        if self.reminder_popup and self.reminder_popup.winfo_exists():
            return

        self.reminder_popup = tk.Toplevel(self)
        self.reminder_popup.title("Atenção! Lembrete!")
        self.reminder_popup.attributes('-topmost', True) 
        self.reminder_popup.configure(background="#FFD700") 
        
        self.reminder_popup.protocol("WM_DELETE_WINDOW", self.hide_agenda_reminder)
        
        # Adiciona um novo estilo para o reminder popup
        self.style.configure("Reminder.TFrame", background="#FFFFFF", borderwidth=3, relief="raised", bordercolor="#FFD700")

        frame = ttk.Frame(self.reminder_popup, style="Reminder.TFrame", padding=15) 
        frame.pack(fill="both", expand=True)
        
        DISPLAY_TIME_MS = 6000 # Aumentei o tempo de exibição para 6 segundos
        first_name = self._get_first_name()
        
        if minutos_restantes == 10:
            titulo_texto = f"🔔 OLÁ, {first_name.upper()}! COMPROMISSO EM 10 MINUTOS!"
            titulo_cor = PRIMARY_BLUE 
            msg_extra = "Prepare-se para o alinhamento! Sua pontualidade é essencial."
        else: 
            titulo_texto = f"🔴 {first_name.upper()}, É HORA! COMPROMISSO AGORA!"
            titulo_cor = DANGER_RED 
            msg_extra = "O compromisso está começando. Vamos nessa!"
            
        ttk.Label(frame, text=titulo_texto, 
                  font=("Segoe UI", 11, "bold"), background="#FFFFFF", foreground=titulo_cor).pack(pady=(0, 5), anchor="center")
        
        ttk.Label(frame, text=f"{descricao}\n{msg_extra}", 
                  font=("Segoe UI", 10), background="#FFFFFF", foreground="#000000", justify=tk.CENTER).pack(pady=5, padx=10, anchor="center")
        
        frame_btns = ttk.Frame(frame, background="#FFFFFF")
        frame_btns.pack(pady=5)
        
        if link:
            btn_open_link = ttk.Button(frame_btns, text="Abrir Link da Reunião", command=lambda: [self.hide_agenda_reminder(), self.abrir_link_url(link)])
            btn_open_link.pack(side=tk.LEFT, padx=5)
        
        btn_close = ttk.Button(frame_btns, text="Entendido!", command=self.hide_agenda_reminder)
        btn_close.pack(side=tk.LEFT if link else tk.TOP, padx=5)

        self.reminder_popup.update_idletasks()
        width = self.reminder_popup.winfo_reqwidth()
        height = self.reminder_popup.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = screen_w - width - 20
        y = screen_h - height - 50
        
        self.reminder_popup.geometry(f'+{x}+{y}')
        
        self.after(DISPLAY_TIME_MS, self.hide_agenda_reminder)


    def hide_agenda_reminder(self):
        if self.reminder_popup and self.reminder_popup.winfo_exists():
            self.reminder_popup.destroy()
            self.reminder_popup = None
            
    def update_time(self):
        """Atualiza o relógio digital e agenda a próxima atualização."""
        now = datetime.now()
        current_time_str = now.strftime("Horário: %H:%M:%S") 
        self.time_var.set(current_time_str)
        
        self.get_next_agenda()
        
        self.after(1000, self.update_time)

    def get_next_agenda(self):
        """Calcula e exibe o próximo compromisso agendado (incluindo a daily)."""
        now = datetime.now()
        next_event = None
        min_time_diff = timedelta(days=365)
        today_weekday_index = now.weekday() # 0=Seg, 6=Dom
        
        # Mapeamento de índices de dias da semana (Python: 0=Seg, 6=Dom) para Nomes
        WEEKDAYS_MAP = {
            0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 
            4: "Sex", 5: "Sáb", 6: "Dom"
        }
        
        agendas_to_check = []
        
        # --- 1. Daily Padrão (Seg-Sex) ---
        daily_time = self.daily_time_var.get().strip()
        if self._validate_time_format(daily_time):
            daily_time_obj = datetime.strptime(daily_time, HORA_FORMATO).time()
            next_daily_time = None
            
            # Procura a Daily para hoje (se for dia útil e ainda não passou)
            current_daily_dt = datetime.combine(now.date(), daily_time_obj)
            if now.weekday() < 5 and current_daily_dt > now:
                 next_daily_time = current_daily_dt
            else:
                 # Procura a Daily para o próximo dia útil
                 next_day = now.date() + timedelta(days=1)
                 while next_day.weekday() >= 5: 
                    next_day += timedelta(days=1)
                 next_daily_time = datetime.combine(next_day, daily_time_obj)

            if next_daily_time:
                 agendas_to_check.append({
                    "data_time_obj": next_daily_time,
                    "descricao": f"Sua Daily - Time {self.team_var.get().strip() if self.team_var.get().strip() else 'sem nome'}",
                    "link": "",
                    "repeticao": "daily_wday" 
                 })

        # --- 2. Agendas Únicas e Recorrentes Customizadas ---
        for item in self.agendas_data:
            agenda_time = None
            repeticao = item.get('repeticao', 'single')

            if repeticao == 'single':
                try:
                    data_hora_str = f"{item['data']} {item['hora']}"
                    dt_obj = datetime.strptime(data_hora_str, f"{DATA_FORMATO_LONGO_PERSIST} {HORA_FORMATO}")
                    if dt_obj > now:
                        agenda_time = dt_obj
                except Exception:
                    continue 

            elif repeticao == 'daily_wday_custom':
                try:
                    dias_indices = ast.literal_eval(item.get('dias_semana', '[]'))
                    hora_obj = datetime.strptime(item['hora'], HORA_FORMATO).time()
                    
                    # Encontra a próxima ocorrência
                    next_occurrence = None
                    for days_ahead in range(7):
                        check_date = now.date() + timedelta(days=days_ahead)
                        check_weekday_index = check_date.weekday()
                        
                        if check_weekday_index in dias_indices:
                            dt_obj = datetime.combine(check_date, hora_obj)
                            
                            if dt_obj > now:
                                next_occurrence = dt_obj
                                break
                    
                    if next_occurrence:
                        agenda_time = next_occurrence
                        
                except Exception:
                    continue

            if agenda_time and (agenda_time - now) < min_time_diff and agenda_time > now:
                min_time_diff = agenda_time - now
                next_event = item
                if repeticao == 'daily_wday_custom' or repeticao == 'daily_wday':
                     next_event['data_time_obj'] = agenda_time # Adiciona a data de ocorrência
            
        if next_event:
            total_seconds = int(min_time_diff.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            
            desc = next_event['descricao']
            desc_display = desc[:20] + "..." if len(desc) > 20 else desc
            
            time_left = ""
            if hours > 0:
                 time_left = f"{hours}h {minutes}m"
            else:
                 time_left = f"{minutes} min"
                 
            # Adiciona o dia da semana/data
            if next_event.get('repeticao') == 'daily_wday' or next_event.get('repeticao') == 'daily_wday_custom':
                 day_name = WEEKDAYS_MAP[next_event['data_time_obj'].weekday()]
                 if next_event['data_time_obj'].date() == now.date():
                      time_info = f"Hoje ({time_left})"
                 else:
                      time_info = f"Próxima {day_name} ({time_left})"
            else: # single
                 date_obj = datetime.strptime(next_event['data'], DATA_FORMATO_LONGO_PERSIST)
                 if date_obj.date() == now.date():
                    time_info = f"Hoje ({time_left})"
                 else:
                    time_info = f"{date_obj.strftime(DATA_FORMATO_CURTO)} ({time_left})"


            self.next_agenda_var.set(f"Próx. Agenda: {desc_display} ({time_info})")
            
        else:
            self.next_agenda_var.set("Próx. Agenda: N/A")


    def save_all_data(self):
        first_name = self._get_first_name()
        # Garante que o perfil atual seja salvo em seu arquivo antes de fechar
        self.salvar_devolutivas_file() 
        
        # Garante que as anotações do widget principal sejam transferidas para a StringVar antes de salvar
        if hasattr(self, 'anotacoes_text'):
             self._update_anotacoes_content(event=None, save_to_var=True)
             self._save_anotacoes_file() # Salva o arquivo de anotações explicitamente
        
        calc_data = {"history": self.calc_history}
        self.salvar_json(ARQUIVO_CALCULADORA, calc_data)
        self.salvar_json(ARQUIVO_AGENDAS, self.agendas_data)
        self.salvar_volumetria_data()
        self.salvar_config() 
        
        # Salva a config do perfil ativo
        self.salvar_json(ARQUIVO_DEVOLUTIVAS_CONFIG, {"active_profile": self.devolutivas_active_profile_name.get()})
        
        self.atualizar_status(f"Todos os seus dados foram salvos! Até logo, {first_name}!")

    def on_closing(self):
        self.app_rodando = False
        try:
            keyboard.unhook_all_hotkeys()
            keyboard.unhook_all()
        except Exception as e:
            print(f"Erro ao desativar hotkeys: {e}")
        
        first_name = self._get_first_name()
        self.atualizar_status(f"Até mais, {first_name}! Encerrando o SmartBPO...")

        self.save_all_data()

        if hasattr(self, 'config_window') and self.config_window and self.config_window.winfo_exists(): self.config_window.destroy()
        if hasattr(self, 'popup_hints') and self.popup_hints and self.popup_hints.winfo_exists(): self.popup_hints.destroy()
        if hasattr(self, 'reminder_popup') and self.reminder_popup and self.reminder_popup.winfo_exists(): self.reminder_popup.destroy()
        if hasattr(self, 'macro_feedback_popup') and self.macro_feedback_popup and self.macro_feedback_popup.winfo_exists(): self.macro_feedback_popup.destroy()
        if hasattr(self, 'metas_window') and self.metas_window and self.metas_window.winfo_exists(): self.metas_window.destroy()
        if hasattr(self, 'standard_calc_window') and self.standard_calc_window and self.standard_calc_window.winfo_exists(): self.standard_calc_window.destroy() # DESTROI NOVO POP-UP
            
        self.quit()
        self.destroy()

# --- Bloco de Execução Principal ---
if __name__ == '__main__':
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        print(f"Erro crítico na inicialização do Tkinter/App: {e}")