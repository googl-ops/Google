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
        
        print(f"🎵 جاري تحميل الصوت: {audio_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"❌ ملف الصوت غير موجود: {audio_path}")
            
        self.y, self.sr = librosa.load(audio_path, sr=None)
        self.duration = librosa.get_duration(y=self.y, sr=self.sr)
        print(f"✅ تم التحميل. المدة: {self.duration:.2f} ثانية")
        
        self.width = 1920
        self.height = 1080
        
    def extract_features(self):
        print("📊 جاري تحليل الصوت...")
        rms = librosa.feature.rms(y=self.y)[0]
        tempo, beats = librosa.beat.beat_track(y=self.y, sr=self.sr)
        return rms, tempo, librosa.frames_to_time(beats, sr=self.sr)
    
    def create_background(self, time, intensity, is_beat=False):
        base_color = (3, 3, 8)
        img = Image.new('RGB', (self.width, self.height), base_color)
        draw = ImageDraw.Draw(img)
        
        for layer in range(4):
            alpha = int(12 + intensity * 20 * (4-layer)/4)
            offset = time * (0.2 + layer * 0.08)
            
            for i in range(6):
                angle = offset + i * (np.pi / 3)
                radius_base = 150 + layer * 80
                
                x = self.width/2 + np.cos(angle) * radius_base * (1 + intensity * 0.5)
                y = self.height/2 + np.sin(angle) * (radius_base * 0.6) * (1 + intensity * 0.3)
                
                circle_radius = int(80 + intensity * 120 + layer * 25)
                color_val = int(8 + intensity * 15)
                color = (color_val//2, color_val//3, color_val//2 + 2)
                
                draw.ellipse(
                    [x-circle_radius, y-circle_radius, x+circle_radius, y+circle_radius], 
                    fill=color
                )
        
        if is_beat:
            pulse = int(100 * intensity)
            border = 15
            draw.rectangle(
                [border, border, self.width-border, self.height-border], 
                outline=(pulse//3, pulse//4, pulse//2), 
                width=2
            )
        
        img = img.filter(ImageFilter.GaussianBlur(radius=3))
        return np.array(img)
    
    def prepare_arabic_text(self, text):
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text
    
    def create_text_clip(self, text, start_time, duration, is_special=False):
        prepared_text = self.prepare_arabic_text(text)
        font_size = 75 if is_special else 68
        
        txt_clip = mp.TextClip(
            prepared_text,
            fontsize=font_size,
            color='#F0F0F0',
            font='Arial-Bold',
            method='caption',
            size=(self.width - 300, 350),
            align='center',
            stroke_color='black',
            stroke_width=4,
            interline=-5
        ).set_start(start_time).set_duration(duration)
        
        txt_clip = txt_clip.set_position(('center', 0.65), relative=True)
        txt_clip = txt_clip.fx(fadein, duration=0.6).fx(fadeout, duration=0.6)
        
        return txt_clip
    
    def generate_video(self, output_path, fps=24):
        print("🎬 بدء إنتاج الفيديو...")
        
        rms, tempo, beat_times = self.extract_features()
        print(f"🎼 tempo: {tempo:.1f} BPM")
        
        print("🖼️ جاري إنشاء الإطارات...")
        frames = []
        num_frames = int(self.duration * fps)
        
        beat_frame_indices = set(int(b * fps) for b in beat_times if int(b * fps) < num_frames)
        
        for i in range(num_frames):
            t = i / fps
            idx = min(int(t * len(rms) / self.duration), len(rms) - 1)
            intensity = rms[idx] / np.max(rms) if np.max(rms) > 0 else 0
            is_beat = i in beat_frame_indices
            
            frame = self.create_background(t, intensity, is_beat)
            frames.append(frame)
            
            if i % 200 == 0 or i == num_frames - 1:
                progress = (i / num_frames) * 100
                print(f"   التقدم: {progress:.1f}%")
        
        print("🎞️ تجميع الخلفية...")
        background_clip = mp.ImageSequenceClip(frames, fps=fps)
        
        text_clips = []
        if self.lyrics_file and os.path.exists(self.lyrics_file):
            print("📜 جاري تحميل الأبيات...")
            with open(self.lyrics_file, 'r', encoding='utf-8') as f:
                verses = [line.strip() for line in f.readlines() if line.strip()]
            
            print(f"✅ تم العثور على {len(verses)} بيتاً")
            verse_duration = self.duration / len(verses)
            
            for i, verse in enumerate(verses):
                start_time = i * verse_duration
                is_special = (i // 4) % 2 == 0
                
                clip = self.create_text_clip(verse, start_time, verse_duration * 0.9, is_special)
                text_clips.append(clip)
                
                if i < 3 or i >= len(verses) - 3:
                    print(f"   بيت {i+1}: {verse[:50]}...")
        
        if text_clips:
            final_video = mp.CompositeVideoClip([background_clip] + text_clips, size=(self.width, self.height))
        else:
            final_video = background_clip
        
        print("🔊 إضافة الصوت...")
        audio_clip = mp.AudioFileClip(self.audio_path)
        final_video = final_video.set_audio(audio_clip)
        
        print(f"💾 حفظ: {output_path}")
        final_video.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            preset='medium',
            threads=4,
            verbose=False,
            logger=None
        )
        
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ تم الحفظ! الحجم: {size_mb:.2f} MB")
        else:
            print("❌ فشل الحفظ!")
            
        return output_path

def main():
    audio_file = "audio.mp3"
    lyrics_file = "lyrics.txt"
    output_file = "poem_video.mp4"
    
    print("🔍 التحقق...")
    if not os.path.exists(audio_file):
        print(f"❌ لم يُعثر على '{audio_file}'")
        print("📁 الملفات:", os.listdir('.'))
        sys.exit(1)
    
    try:
        visualizer = PoetryVisualizer(audio_file, lyrics_file)
        visualizer.generate_video(output_file)
        print("\n🎉 تم بنجاح!")
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
