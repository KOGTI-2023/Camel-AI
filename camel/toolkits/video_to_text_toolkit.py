import os
import yt_dlp
import whisper
import subprocess
import multiprocessing
from queue import Queue


def get_current_directory():
    return os.path.dirname(os.path.abspath(__file__))


def validate_audio_file(file_path):
    result = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0


def download_chunk(video_url, start_time, end_time, chunk_index,
                   current_directory, download_queue):
    audio_filename = os.path.join(current_directory,
                                  f'audio_chunk_{chunk_index}.mp3')
    ydl_opts = {
        'format':
        'bestaudio/best',
        'outtmpl':
        os.path.join(current_directory, f'audio_chunk_{chunk_index}'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'postprocessor_args': ['-ss',
                               str(start_time), '-to',
                               str(end_time)],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    if not os.path.exists(audio_filename) or os.path.getsize(
            audio_filename) == 0:
        raise FileNotFoundError(f"下载的音频文件 {audio_filename} 不存在或是空文件.")

    if not validate_audio_file(audio_filename):
        raise ValueError(f"下载的音频文件 {audio_filename} 无效或损坏.")

    download_queue.put((chunk_index, audio_filename))


def transcribe_chunk(chunk_index, audio_filename, model, current_directory):
    result = model.transcribe(audio_filename)
    os.remove(audio_filename)
    text = result["text"]

    output_filename = os.path.join(current_directory,
                                   f'transcript_chunk_{chunk_index}.txt')
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(text)


def download_process(video_url, chunk_duration, video_length, download_queue):
    current_directory = get_current_directory()
    chunk_index = 0
    start_time = 0

    while start_time < video_length:
        end_time = min(start_time + chunk_duration, video_length)
        download_chunk(video_url, start_time, end_time, chunk_index,
                       current_directory, download_queue)
        chunk_index += 1
        start_time = end_time

    # Signal the end of download
    download_queue.put(None)


def transcribe_process(model, download_queue):
    current_directory = get_current_directory()

    while True:
        item = download_queue.get()
        if item is None:
            break
        chunk_index, audio_filename = item
        transcribe_chunk(chunk_index, audio_filename, model, current_directory)


def main(video_url, chunk_duration, video_length):
    download_queue = multiprocessing.Queue()
    model = whisper.load_model("base")

    download_proc = multiprocessing.Process(
        target=download_process,
        args=(video_url, chunk_duration, video_length, download_queue))
    transcribe_proc = multiprocessing.Process(target=transcribe_process,
                                              args=(model, download_queue))

    download_proc.start()
    transcribe_proc.start()

    download_proc.join()
    transcribe_proc.join()


if __name__ == "__main__":
    video_url = 'https://www.youtube.com/watch?v=5LhvT1TZig0&t=165s'
    chunk_duration = 30
    video_length = 570  # 假设视频长度为 570 秒，实际情况需要从视频信息中获取
    main(video_url, chunk_duration, video_length)
