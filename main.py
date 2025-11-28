import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os

# Установка режима внешнего вида (Система, Светлая, Темная)
ctk.set_appearance_mode("System")
# Установка цветовой темы (По умолчанию: Синяя)
ctk.set_default_color_theme("blue") 

# --- Основная логика выполнения команды FFmpeg (остается прежней) ---
def run_ffmpeg_command(command, command_description="Задача FFmpeg"):
    
    # Проверка наличия FFmpeg в PATH
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        messagebox.showerror("Ошибка", "FFmpeg не найден.\nУбедитесь, что FFmpeg установлен и добавлен в переменную среды PATH.")
        return

    try:
        # Выполнение команды (используем shell=True для удобства с путями в Windows)
        messagebox.showinfo(command_description, f"Выполняется команда:\n{command}")
        
        result = subprocess.run(
            command,
            check=True,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        output_message = f"✅ Команда «{command_description}» успешно завершена!\n\n"
        messagebox.showinfo("Успех", output_message)

    except subprocess.CalledProcessError as e:
        error_output = e.stderr or e.stdout
        error_message = f"❌ Ошибка при выполнении {command_description}:\n\n"
        error_message += f"Команда:\n{e.cmd}\n\n"
        error_message += f"Сообщение FFmpeg (фрагмент):\n{error_output[-1000:]}"
        messagebox.showerror("Ошибка FFmpeg", error_message)
    except Exception as e:
        messagebox.showerror("Неизвестная ошибка", f"Произошла непредвиденная ошибка: {e}")


# --- Функции для выбора файлов (используют стандартный tkinter filedialog) ---
def select_input_file(entry_widget):
    filepath = filedialog.askopenfilename()
    if filepath:
        entry_widget.delete(0, ctk.END)
        entry_widget.insert(0, filepath)

def select_output_file(entry_widget, default_extension):
    input_path = entry_widget.get()
    initial_dir = os.path.dirname(input_path) if os.path.exists(input_path) else os.path.expanduser("~")
    
    filepath = filedialog.asksaveasfilename(
        defaultextension=default_extension,
        initialdir=initial_dir,
        filetypes=[(f"Файл {default_extension}", f"*{default_extension}"), ("Все файлы", "*.*")]
    )
    if filepath:
        entry_widget.delete(0, ctk.END)
        entry_widget.insert(0, filepath)

# --- Генераторы команд FFmpeg ---
def generate_video_conversion_command(input_file, output_file, hardware_accel):
    
    command = 'ffmpeg '

    if hardware_accel == "NVIDIA (NVENC)":
        command += '-vsync 0 -hwaccel cuda '
        video_codec_params = '-c:v h264_nvenc -b:v 4M '
    elif hardware_accel == "AMD (AMF)":
        command += '-vsync 0 -hwaccel qsv ' 
        video_codec_params = '-c:v h264_amf -b:v 4M '
    else: # CPU (libx264)
        command += ''
        video_codec_params = '-c:v libx264 -preset medium -crf 23 '
        
    command += f'-i "{input_file}" '
    command += video_codec_params
        
    command += '-pix_fmt yuv420p -c:a aac -b:a 128k '
    command += f'"{output_file}"'
    
    return command

def generate_video_compress_command(input_file, output_file, hardware_accel):
    
    # 1. Начинаем с FFmpeg и параметров ускорения (если выбрано)
    command = 'ffmpeg '

    if hardware_accel == "NVIDIA (NVENC)":
        # Устанавливаем аппаратный декодер перед -i
        command += '-vsync 0 -hwaccel cuda ' 
        video_codec_params = '-c:v h264_nvenc -b:v 2M '
    elif hardware_accel == "AMD (AMF)":
        # Для AMD/Intel QSV также размещаем перед -i (хотя QSV может быть сложнее настроить)
        command += '-vsync 0 -hwaccel qsv ' 
        video_codec_params = '-c:v h264_amf -b:v 2M '
    else: # CPU (libx264)
        # Для CPU просто начинаем с -i
        command += ''
        video_codec_params = '-c:v libx264 -preset veryslow -crf 28 '
        
    # 2. Добавляем входной файл
    command += f'-i "{input_file}" '

    # 3. Добавляем параметры кодека (которые влияют на выход)
    command += video_codec_params
        
    # 4. Добавляем параметры аудио и выходной файл
    command += '-c:a aac -b:a 64k ' # Снижаем битрейт аудио
    command += f'"{output_file}"'
    
    return command

def generate_audio_conversion_command(input_file, output_file):
    command = f'ffmpeg -i "{input_file}" -vn -c:a libmp3lame -b:a 320k "{output_file}"'
    return command

def generate_video_trim_command(input_file, output_file, start_time, end_time):
    # Ускорение не используется, так как это -c copy
    command = f'ffmpeg -i "{input_file}" -ss {start_time} -to {end_time} -c copy "{output_file}"'
    return command


# --- Класс для создания главного окна GUI на CustomTkinter ---
class FFmpegApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("FFmpeg GUI")
        self.geometry("850x550")
        
        # Настройка сетки
        self.grid_rowconfigure(0, weight=1)  # Задаем растягиваемость для вкладок
        self.grid_columnconfigure(0, weight=1)

        # Создание вкладок (CTkTabview)
        self.tab_view = ctk.CTkTabview(self, width=800)
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Добавление вкладок
        self.tab_view.add("Видео → MP4")
        self.tab_view.add("Уменьшение размера")
        self.tab_view.add("Аудио → MP3")
        self.tab_view.add("Обрезка видео")
        self.tab_view.add("Установка & Info")

        # Наполнение вкладок
        self.create_video_conversion_tab(self.tab_view.tab("Видео → MP4"))
        self.create_video_compress_tab(self.tab_view.tab("Уменьшение размера"))
        self.create_audio_conversion_tab(self.tab_view.tab("Аудио → MP3"))
        self.create_video_trim_tab(self.tab_view.tab("Обрезка видео"))
        self.create_instructions_tab(self.tab_view.tab("Установка & Info"))

    # --- Вспомогательные функции для создания виджетов CTk ---

    def create_file_selector(self, parent, label_text, entry_var, default_ext=None):
        """Создает поле для ввода файла с кнопкой выбора."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(pady=10, padx=10, fill='x')
        
        ctk.CTkLabel(frame, text=label_text).pack(side=ctk.LEFT, padx=10)
        
        entry = ctk.CTkEntry(frame, textvariable=entry_var, width=350)
        entry.pack(side=ctk.LEFT, fill='x', expand=True, padx=5)
        
        if default_ext:
            button_text = "Сохранить как..."
            command_func = lambda: select_output_file(entry, default_ext)
        else:
            button_text = "Выбрать файл"
            command_func = lambda: select_input_file(entry)
            
        ctk.CTkButton(frame, text=button_text, command=command_func, width=120).pack(side=ctk.RIGHT)
        return entry # Возвращаем entry для возможности манипуляции

    def create_hardware_accelerator_selector(self, parent, accel_var):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(pady=10, padx=10, fill='x')

        ctk.CTkLabel(frame, text="Аппаратное ускорение:").pack(side=ctk.LEFT, padx=10)
        
        options = ["CPU (libx264)", "NVIDIA (NVENC)", "AMD (AMF)"]
        
        accel_combobox = ctk.CTkComboBox(frame, 
                                         variable=accel_var, 
                                         values=options, 
                                         width=200, 
                                         state="readonly")
        accel_combobox.pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkLabel(frame, text=" (GPU ускоряет кодирование)").pack(side=ctk.LEFT, padx=5)

    # --- Создание вкладок ---

    def create_instructions_tab(self, tab):
        text_content = (
            "Установка FFmpeg\n\n"
            "Для работы этого GUI FFmpeg должен быть установлен и доступен в PATH.\n\n"
            "1. Откройте PowerShell от имени администратора.\n"
            "2. Выполните следующие команды:\n"
            "   – Set-ExecutionPolicy RemoteSigned -Scope CurrentUser (Если не делали ранее)\n"
            "   – iwr -useb get.scoop.sh | iex (Установка Scoop)\n"
            "   – scoop install ffmpeg (Установка FFmpeg)\n\n"
        )
        label = ctk.CTkLabel(tab, text=text_content, justify=ctk.LEFT, anchor="nw", wraplength=750)
        label.pack(padx=20, pady=20, fill="both", expand=True)

    def create_video_conversion_tab(self, tab):
        # Переменные
        self.conv_input_var = ctk.StringVar()
        self.conv_output_var = ctk.StringVar()
        self.conv_accel_var = ctk.StringVar(value="CPU (libx264)")
        
        # Виджеты
        self.create_file_selector(tab, "Входной файл (любое расширение):", self.conv_input_var)
        self.create_file_selector(tab, "Выходной файл:", self.conv_output_var, default_ext=".mp4")
        self.create_hardware_accelerator_selector(tab, self.conv_accel_var)
        
        # Кнопка запуска
        run_button = ctk.CTkButton(tab, text="🚀 Запустить конвертацию (MP4 H.264/AAC)", 
                                   command=self.run_video_conversion, 
                                   height=40, font=ctk.CTkFont(size=14, weight="bold"))
        run_button.pack(pady=20)

    def run_video_conversion(self):
        input_file = self.conv_input_var.get()
        output_file = self.conv_output_var.get()
        accel = self.conv_accel_var.get()
        
        if not input_file or not output_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите входной и выходной файлы.")
            return

        command = generate_video_conversion_command(input_file, output_file, accel)
        run_ffmpeg_command(command, "Конвертация видео в MP4")

    def create_video_compress_tab(self, tab):
        # Переменные
        self.comp_input_var = ctk.StringVar()
        self.comp_output_var = ctk.StringVar()
        self.comp_accel_var = ctk.StringVar(value="CPU (libx264)")
        
        # Виджеты
        self.create_file_selector(tab, "Входной файл:", self.comp_input_var)
        self.create_file_selector(tab, "Выходной файл:", self.comp_output_var, default_ext=".mp4")
        self.create_hardware_accelerator_selector(tab, self.comp_accel_var)
        
        # Кнопка запуска
        run_button = ctk.CTkButton(tab, text="🚀 Запустить сжатие (CRF 28, для Telegram)", 
                                   command=self.run_video_compress, 
                                   height=40, font=ctk.CTkFont(size=14, weight="bold"), 
                                   fg_color="darkgreen", hover_color="#2D7F3E")
        run_button.pack(pady=20)

    def run_video_compress(self):
        input_file = self.comp_input_var.get()
        output_file = self.comp_output_var.get()
        accel = self.comp_accel_var.get()
        
        if not input_file or not output_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите входной и выходной файлы.")
            return

        command = generate_video_compress_command(input_file, output_file, accel)
        run_ffmpeg_command(command, "Уменьшение размера видео")

    def create_audio_conversion_tab(self, tab):
        # Переменные
        self.audio_input_var = ctk.StringVar()
        self.audio_output_var = ctk.StringVar()
        
        # Виджеты
        self.create_file_selector(tab, "Входной файл (любое расширение):", self.audio_input_var)
        self.create_file_selector(tab, "Выходной файл:", self.audio_output_var, default_ext=".mp3")
        
        # Кнопка запуска
        run_button = ctk.CTkButton(tab, text="🚀 Запустить конвертацию аудио в MP3 (320k)", 
                                   command=self.run_audio_conversion, 
                                   height=40, font=ctk.CTkFont(size=14, weight="bold"), 
                                   fg_color="purple", hover_color="#631C82")
        run_button.pack(pady=20)

    def run_audio_conversion(self):
        input_file = self.audio_input_var.get()
        output_file = self.audio_output_var.get()
        
        if not input_file or not output_file:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите входной и выходной файлы.")
            return

        command = generate_audio_conversion_command(input_file, output_file)
        run_ffmpeg_command(command, "Конвертация аудио в MP3")

    def create_video_trim_tab(self, tab):
        # Переменные
        self.trim_input_var = ctk.StringVar()
        self.trim_output_var = ctk.StringVar()
        self.trim_start_var = ctk.StringVar(value="00:00:05.0")
        self.trim_end_var = ctk.StringVar(value="00:00:15.0")
        
        # Виджеты
        self.create_file_selector(tab, "Входной файл:", self.trim_input_var)
        self.create_file_selector(tab, "Выходной файл:", self.trim_output_var, default_ext=".mp4")
        
        # Ввод таймкодов
        time_frame = ctk.CTkFrame(tab, fg_color="transparent")
        time_frame.pack(pady=10, padx=10, fill='x')
        
        ctk.CTkLabel(time_frame, text="Начало (HH:MM:SS.ms):").pack(side=ctk.LEFT, padx=10)
        ctk.CTkEntry(time_frame, textvariable=self.trim_start_var, width=150).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkLabel(time_frame, text="Конец (HH:MM:SS.ms):").pack(side=ctk.LEFT, padx=10)
        ctk.CTkEntry(time_frame, textvariable=self.trim_end_var, width=150).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkLabel(tab, text="⚠︎ Обрезка использует -c copy: быстро, без потерь, но GPU ускорение не применяется.").pack(pady=5)
        
        # Кнопка запуска
        run_button = ctk.CTkButton(tab, text="🚀 Запустить обрезку (-c copy)", 
                                   command=self.run_video_trim, 
                                   height=40, font=ctk.CTkFont(size=14, weight="bold"), 
                                   fg_color="red", hover_color="#CC0000")
        run_button.pack(pady=20)

    def run_video_trim(self):
        input_file = self.trim_input_var.get()
        output_file = self.trim_output_var.get()
        start_time = self.trim_start_var.get()
        end_time = self.trim_end_var.get()
        
        if not input_file or not output_file or not start_time or not end_time:
            messagebox.showwarning("Предупреждение", "Пожалуйста, заполните все поля.")
            return

        command = generate_video_trim_command(input_file, output_file, start_time, end_time)
        run_ffmpeg_command(command, "Обрезка видео")


# --- Запуск приложения ---
if __name__ == '__main__':
    app = FFmpegApp()
    app.mainloop()