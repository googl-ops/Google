import librosa
import numpy as np
import moviepy.editor as mp
from moviepy.video.fx.all import fadein, fadeout
from PIL import Image, ImageDraw, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
import os
import sys

class PoetryVisualizer:
    def __init__(self, audio_path, lyrics_file=None):
        self.audio_path = audio_path
        self.lyrics_file = lyrics_file
        
        print(f"تحميل الصوت: {audio_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"ملف الصوت غير موجود: {audio_path}")
            
        self.y, self.sr = librosa.load(audio_path, sr=None)
        self.duration = librosa.get_duration(y=self.y, sr=self.sr)
        print(f"المدة: {self.duration:.2f} ثانية")
        
        self.width = 1920
        self.height = 1080
        
    def extract_features(self):
        print("تحليل الصوت...")
        rms = librosa.feature.rms(y=self.y)[0]
        tempo, beats = librosa.beat.beat_track(y=self.y, sr=self.sr)
        beat_times = librosa.frames_to_time(beats, sr=self.sr)
        print(f"الإيقاع: {tempo:.1f} BPM")
        return rms, beat_times
    
    def create_background(self, time, intensity, is_beat):
        img = Image.new('RGB', (self.width, self.height), (3, 3, 8))
        draw = ImageDraw.Draw(img)
        
        for layer in range(4):
            offset = time * (0.2 + layer * 0.08)
            for i in range(6):
                angle = offset + i * (np.pi / 3)
                x = self.width/2 + np.cos(angle) * (150 + layer*80) * (1 + intensity*0.5)
                y = self.height/2 + np.sin(angle) * (150 + layer*80)*0.6 * (1 + intensity*0.3)
                radius = int(80 + intensity*120 + layer*25)
                color_val = int(8 + intensity*15)
                color = (color_val//2, color_val//3, color_val//2+2)
                draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=color)
        
        if is_beat:
            pulse = int(100*intensity)
            draw.rectangle([15, 15, self.width-15, self.height-15], 
                          outline=(pulse//3, pulse//4, pulse//2), width=2)
        
        return np.array(img.filter(ImageFilter.GaussianBlur(radius=3)))
    
    def prepare_arabic_text(self, text):
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text
    
    def create_text_clip(self, text, start_time, duration, is_special):
        prepared = self.prepare_arabic_text(text)
        font_size = 75 if is_special else 68
        
        clip = mp.TextClip(
            prepared,
            fontsize=font_size,
            color='#F0F0F0',
            font='Arial-Bold',
            method='caption',
            size=(self.width-300, 350),
            align='center',
            stroke_color='black',
            stroke_width=4,
            interline=-5
        ).set_start(start_time).set_duration(duration)
        
        clip = clip.set_position(('center', 0.65), relative=True)
        clip = clip.fx(fadein, duration=0.6).fx(fadeout, duration=0.6)
        return clip
    
    def generate_video(self, output_path, fps=24):
        print("إنشاء الفيديو...")
        
        rms, beat_times = self.extract_features()
        num_frames = int(self.duration * fps)
        frames = []
        
        beat_frame_indices = set(int(b * fps) for b in beat_times if int(b * fps) < num_frames)
        
        for i in range(num_frames):
            t = i / fps
            idx = min(int(t * len(rms) / self.duration), len(rms) - 1)
            intensity = rms[idx] / np.max(rms) if np.max(rms) > 0 else 0
            is_beat = i in beat_frame_indices
            
            frame = self.create_background(t, intensity, is_beat)
            frames.append(frame)
            
            if i % 200 == 0:
                print(f"التقدم: {i/num_frames*100:.1f}%")
        
        print("تجميع الفيديو...")
        background = mp.ImageSequenceClip(frames, fps=fps)
        
        text_clips = []
        if self.lyrics_file and os.path.exists(self.lyrics_file):
            print("تحميل الأبيات...")
            with open(self.lyrics_file, 'r', encoding='utf-8') as f:
                verses = [line.strip() for line in f.readlines() if line.strip()]
            
            print(f"عدد الأبيات: {len(verses)}")
            verse_duration = self.duration / len(verses)
            
            for i, verse in enumerate(verses):
                start = i * verse_duration
                is_special = (i // 4) % 2 == 0
                clip = self.create_text_clip(verse, start, verse_duration * 0.9, is_special)
                text_clips.append(clip)
        
        if text_clips:
            video = mp.CompositeVideoClip([background] + text_clips, size=(self.width, self.height))
        else:
            video = background
        
        print("إضافة الصوت...")
        audio = mp.AudioFileClip(self.audio_path)
        final = video.set_audio(audio)
        
        print(f"حفظ: {output_path}")
        final.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            threads=4,
            verbose=False,
            logger=None
        )
        
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"تم بنجاح! الحجم: {size_mb:.2f} ميجابايت")
        else:
            print("فشل الحفظ!")
        
        return output_path

def main():
    audio_file = "audio.mp3"
    lyrics_file = "lyrics.txt"
    output_file = "poem_video.mp4"
    
    print("التحقق من الملفات...")
    if not os.path.exists(audio_file):
        print(f"خطأ: لم يُعثر على {audio_file}")
        print("الملفات المتوفرة:", os.listdir('.'))
        sys.exit(1)
    
    try:
        visualizer = PoetryVisualizer(audio_file, lyrics_file)
        visualizer.generate_video(output_file)
        print("\nاكتمل بنجاح!")
    except Exception as e:
        print(f"\nخطأ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
