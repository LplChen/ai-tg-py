import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

def check_ffmpeg():
    """检查系统是否安装了 FFmpeg"""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except FileNotFoundError:
        return False

def convert_gif_to_webm(input_path, output_path):
    """
    使用 FFmpeg 将 GIF 转换为 Telegram 兼容的 WebM
    自动调整 CRF 以确保文件大小小于 32KB
    """
    
    # Telegram 限制: 32 KB. 为了安全起见，我们设定目标为 31 KB
    MAX_SIZE = 31 * 1024
    
    # 起始 CRF 45 (中质量)，最大 CRF 55 (低质量)
    # 每次重试增加 5
    current_crf = 45
    
    # 构建 FFmpeg 滤镜字符串
    # 1. format=rgba: 【关键修复】先将 GIF 转换为 RGBA 格式，防止缩放时丢失透明通道
    # 2. fps=30: 强制帧率
    # 3. scale: 缩放图片，使长边为100，保持纵横比
    # 4. pad: 将画布扩展为 100x100，居中，背景透明 (color=0x00000000)
    filter_complex = (
        "format=rgba,"
        "fps=30,"
        "scale=100:100:force_original_aspect_ratio=decrease,"
        "pad=100:100:(ow-iw)/2:(oh-ih)/2:color=0x00000000"
    )

    while current_crf <= 55:
        cmd = [
            "ffmpeg",
            "-y",               # 覆盖输出文件
            "-i", input_path,   # 输入文件
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",
            "-vf", filter_complex,
            "-b:v", "0",
            "-crf", str(current_crf),       # 动态调整 CRF
            "-an",              # 去除音频
            "-metadata:s:v:0", "alpha_mode=1", # 标记 Alpha 模式
            "-auto-alt-ref", "0", # 关闭自动作为参考帧，有时能提高透明度兼容性
            output_path
        ]

        try:
            # 运行转换命令，不弹出控制台窗口 (Windows特定)
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            process = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                startupinfo=startupinfo,
                encoding='utf-8'
            )
            
            if process.returncode != 0:
                print(f"Error converting {input_path}: {process.stderr}")
                return False
            
            # 检查文件大小
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size <= MAX_SIZE:
                    print(f"Success: {os.path.basename(input_path)} -> {file_size/1024:.2f}KB (CRF {current_crf})")
                    return True
                else:
                    print(f"File too large ({file_size/1024:.2f}KB) with CRF {current_crf}. Retrying with higher compression...")
                    current_crf += 5
            else:
                return False

        except Exception as e:
            print(f"Exception for {input_path}: {str(e)}")
            return False

    print(f"Failed: {os.path.basename(input_path)} could not be compressed under 32KB even with CRF 55.")
    return False

def select_folder_and_convert():
    if not check_ffmpeg():
        messagebox.showerror("错误", "未检测到 FFmpeg。\n请先安装 FFmpeg 并将其添加到系统 PATH 环境变量中。")
        return

    root = tk.Tk()
    root.withdraw() # 隐藏主窗口

    folder_path = filedialog.askdirectory(title="选择包含透明 GIF 的文件夹")
    
    if not folder_path:
        return

    # 创建输出文件夹
    output_dir = os.path.join(folder_path, "webm_output")
    os.makedirs(output_dir, exist_ok=True)

    files = [f for f in os.listdir(folder_path) if f.lower().endswith(".gif")]
    
    if not files:
        messagebox.showinfo("提示", "所选文件夹中没有 GIF 文件。")
        return

    success_count = 0
    fail_count = 0

    # 创建进度窗口
    progress_window = tk.Toplevel()
    progress_window.title("转换中...")
    progress_window.geometry("300x150")
    label = tk.Label(progress_window, text="正在初始化...", pady=20)
    label.pack()

    for i, filename in enumerate(files):
        label.config(text=f"正在处理 ({i+1}/{len(files)}):\n{filename}")
        progress_window.update()

        input_full_path = os.path.join(folder_path, filename)
        # 输出文件名改为 .webm
        output_filename = os.path.splitext(filename)[0] + ".webm"
        output_full_path = os.path.join(output_dir, output_filename)

        if convert_gif_to_webm(input_full_path, output_full_path):
            success_count += 1
        else:
            fail_count += 1

    progress_window.destroy()
    
    result_msg = f"处理完成！\n\n成功: {success_count}\n失败: {fail_count}\n\n文件已保存至:\n{output_dir}"
    messagebox.showinfo("完成", result_msg)

if __name__ == "__main__":
    select_folder_and_convert()