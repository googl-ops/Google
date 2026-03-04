import librosa  # تم تصحيح الحرف الأول هنا
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
        
        print(f"🎵 تحميل الصوت: {audio_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"❌ ملف الصوت غير موجود: {audio_path}")
            
        self.y, self.sr = librosa.load(audio_path, sr=None)
        self.duration = librosa.get_duration(y=self.y, sr=self.sr)
        print(f"✅ المدة: {self.duration:.2f} ثانية")
        
        self.width = 1920
        self.height = 1080
        
    def extract_features(self):
        print("📊 تحليل الصوت واستخراج الإيقاع...")
        rms = librosa.feature.rms(y=self.y)[0]
        tempo, beats = librosa.beat.beat_track(y=self.y, sr=self.sr)
        beat_times = librosa.frames_to_time(beats, sr=self.sr)
        print(f"🎼 الإيقاع المكتشف: {tempo:.1f} BPM")
        return rms, beat_times
    
    def create_background(self, time, intensity, is_beat):
        # لون خلفية داكن مستوحى من ليل الصوفية
        img = Image.new('RGB', (self.width, self.height), (3, 3, 12))
        draw = ImageDraw.Draw(img)
        
        for layer in range(4):
            offset = time * (0.15 + layer * 0.05)
            for i in range(6):
                angle = offset + i * (np.pi / 3)
                radius_base = (180 + layer * 90) * (1 + intensity * 0.4)
                x = self.width/2 + np.cos(angle) * radius_base
                y = self.height/2 + np.sin(angle) * (radius_base * 0.6)
                
                # دوائر متوهجة مع الإيقاع
                circle_radius = int(70 + intensity * 130 + layer * 20)
                color_val = int(10 + intensity * 25)
                # ألوان سماوية خافتة
                color = (color_val//2, color_val//2, color_val + 10)
                draw.ellipse([x-circle_radius, y-circle_radius, x+circle_radius, y+circle_radius], fill=color)
        
        if is_beat:
            # نبضة عند كل ضربة دف
            draw.rectangle([10, 10, self.width-10, self.height-10], 
                          outline=(60, 60, 100), width=3)
        
        return np.array(img.filter(ImageFilter.GaussianBlur(radius=5)))
    
    def prepare_arabic_text(self, text):
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text
    
    def create_text_clip(self, text, start_time, duration, is_special):
        prepared = self.prepare_arabic_text(text)
        # استخدام خط متوفر في Linux/GitHub
        font_name = 'DejaVu-Sans-Bold' 
        font_size = 72 if is_special else 65
        
        clip = mp.TextClip(
            prepared,
            fontsize=font_size,
            color='#E0E0E0',
            font=font_name,
            method='caption',
            size=(self.width-400, 400),
            align='center',
            stroke_color='black',
            stroke_width=2
        ).set_start(start_time).set_duration(duration)
        
        clip = clip.set_position(('center', 0.65), relative=True)
        clip = clip.fx(fadein, duration=0.8).fx(fadeout, duration=0.8)
        return clip
    
    def generate_video(self, output_path, fps=24):
        print("🎬 جاري معالجة المشاهد البصرية...")
        
        rms, beat_times = self.extract_features()
        num_frames = int(self.duration * fps)
        frames = []
        
        beat_frame_indices = set(int(b * fps) for b in beat_times if int(b * fps) < num_frames)
        
        for i in range(num_frames):
            t = i / fps
            idx = min(int(t * len(rms) / self.duration), len(rms) - 1)
            intensity = rms[idx] / np.max(rms) if np.max(rms) > 0 else 0
            is_beat = i in beat_frame_indices
            
            frames.append(self.create_background(t, intensity, is_beat))
            if i % 300 == 0:
                print(f"⏳ تقدم الإنتاج: {i/num_frames*100:.1f}%")
        
        background = mp.ImageSequenceClip(frames, fps=fps)
        
        text_clips = []
        if self.lyrics_file and os.path.exists(self.lyrics_file):
            with open(self.lyrics_file, 'r', encoding='utf-8') as f:
                verses = [line.strip() for line in f.readlines() if line.strip()]
            
            verse_duration = self.duration / len(verses)
            for i, verse in enumerate(verses):
                start = i * verse_duration
                is_special = (i // 2) % 2 == 0
                text_clips.append(self.create_text_clip(verse, start, verse_duration * 0.95, is_special))
        
        print("🎵 دمج الصوت وتصدير الملف النهائي...")
        final = mp.CompositeVideoClip([background] + text_clips).set_audio(mp.AudioFileClip(self.audio_path))
        
        final.write_videofile(output_path, fps=fps, codec='libx264', audio_codec='aac', threads=4, logger=None)
        print(f"✨ اكتمل الإبداع! الفيديو جاهز باسم: {output_path}")

def main():
    try:
        viz = PoetryVisualizer("audio.mp3", "lyrics.txt")
        viz.generate_video("poem_video.mp4")
    except Exception as e:
        print(f"❌ خطأ: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
