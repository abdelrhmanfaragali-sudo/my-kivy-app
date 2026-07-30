"""
تطبيق تحميل قوائم تشغيل يوتيوب - نسخة KivyMD للأندرويد
YouTube Playlist Downloader - KivyMD Android App
"""

import os
import re
import json
import time
import shutil
import zipfile
import threading
import subprocess
from datetime import datetime
from functools import partial

# Kivy imports
import kivy
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock, mainthread
from kivy.utils import platform
from kivy.properties import (
    StringProperty, BooleanProperty, NumericProperty, 
    ObjectProperty, ListProperty
)

# KivyMD imports
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import MDList, OneLineIconListItem, CheckboxLeftWidget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDIconButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDToolbar
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.dropdownitem import MDDropDownItem
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import Snackbar

# Android permissions
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    request_permissions([
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.INTERNET
    ])

# ============================================================================
# إعدادات وتكوينات
# ============================================================================

QUALITY_VALUES = ["أعلى جودة (Best)", "1080p", "720p", "480p", "360p", "صوت فقط (MP3)"]
QUALITY_TO_HEIGHT = {
    "أعلى جودة (Best)": None,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "صوت فقط (MP3)": "audio",
}

COLORS = {
    'primary': '#FF3B3B',
    'primary_dark': '#CC2E2E',
    'bg': '#1a1a1f',
    'card': '#232329',
    'text': '#FFFFFF',
    'text_secondary': '#8a8a93',
    'success': '#3ddc84',
    'warning': '#f5a623',
    'danger': '#ff6b6b',
}

# ============================================================================
# دوال مساعدة
# ============================================================================

def sanitize_filename(name: str) -> str:
    """تنظيف اسم الملف من الأحرف غير المسموحة"""
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.strip(' .')
    return name or 'playlist'

def format_bytes(num_bytes) -> str:
    """تحويل البايتات إلى نص مقروء"""
    if not num_bytes:
        return "0 B"
    num_bytes = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"

def get_download_path():
    """الحصول على مسار التحميل المناسب حسب النظام"""
    if platform == 'android':
        try:
            return primary_external_storage_path()
        except:
            return '/storage/emulated/0/Download'
    else:
        return os.path.join(os.path.expanduser('~'), 'Downloads')

# ============================================================================
# استثناءات مخصصة
# ============================================================================

class DownloadCancelled(Exception):
    pass

# ============================================================================
# شاشة التطبيق الرئيسية
# ============================================================================

class MainScreen(MDScreen):
    """الشاشة الرئيسية للتطبيق"""
    
    # خصائص المراقبة
    is_downloading = BooleanProperty(False)
    is_paused = BooleanProperty(False)
    progress_value = NumericProperty(0)
    status_text = StringProperty('جاهز للتحميل')
    download_btn_text = StringProperty('⬇ تحميل')
    download_btn_disabled = BooleanProperty(True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # حالة التطبيق
        self.playlist_entries = []
        self.selected_entries = []
        self.quality = '1080p'
        self.zip_mode = False
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.ffmpeg_ready = False
        self.estimation_in_progress = False
        self.videos_done = 0
        self.total_selected = 0
        self.failed_videos = []
        self.completed_bytes = 0
        self.last_output_path = ""
        
        # متغيرات Kivy
        self.video_checkboxes = {}
        self.video_estimates = {}
        self.quality_menu = None
        self.dialog = None
        
        # بناء الواجهة
        self.build_ui()
        
        # تجهيز ffmpeg في الخلفية
        threading.Thread(target=self._prepare_ffmpeg, daemon=True).start()
    
    def build_ui(self):
        """بناء واجهة المستخدم"""
        # الحاوية الرئيسية
        main_layout = MDBoxLayout(
            orientation='vertical',
            md_bg_color=COLORS['bg'],
            spacing=0
        )
        
        # شريط العنوان
        toolbar = MDToolbar(
            title='مُحمّل يوتيوب',
            md_bg_color=COLORS['primary'],
            elevation=4,
            right_action_items=[['refresh', lambda x: self.clear_all()]],
            left_action_items=[['menu', lambda x: self.show_menu()]]
        )
        toolbar.title_align = 'center'
        main_layout.add_widget(toolbar)
        
        # محتوى قابل للتمرير
        scroll = MDScrollView()
        content = MDBoxLayout(
            orientation='vertical',
            spacing=10,
            padding=[10, 10, 10, 10],
            size_hint_y=None,
            adaptive_height=True
        )
        
        # ====== بطاقة الرابط ======
        url_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            adaptive_height=True,
            md_bg_color=COLORS['card'],
            radius=[10, 10, 10, 10],
            padding=10,
            spacing=10
        )
        
        url_label = MDLabel(
            text='رابط قائمة التشغيل',
            font_style='H6',
            theme_text_color='Custom',
            text_color=COLORS['text'],
            halign='center'
        )
        url_card.add_widget(url_label)
        
        self.url_input = MDTextField(
            hint_text='https://www.youtube.com/playlist?list=...',
            mode='round',
            size_hint_x=1,
            font_size='14sp',
            helper_text_mode='on_focus',
            multiline=False
        )
        url_card.add_widget(self.url_input)
        
        # أزرار الرابط
        url_buttons = MDBoxLayout(
            orientation='horizontal',
            spacing=10,
            size_hint_y=None,
            height='48dp'
        )
        
        self.fetch_btn = MDRaisedButton(
            text='جلب الفيديوهات',
            md_bg_color=COLORS['primary'],
            text_color='white',
            font_size='14sp',
            on_release=self.fetch_playlist
        )
        url_buttons.add_widget(self.fetch_btn)
        
        paste_btn = MDRaisedButton(
            text='لصق',
            md_bg_color=COLORS['card'],
            text_color=COLORS['text'],
            font_size='14sp',
            on_release=self.paste_from_clipboard
        )
        url_buttons.add_widget(paste_btn)
        
        url_card.add_widget(url_buttons)
        
        self.playlist_info_label = MDLabel(
            text='',
            halign='center',
            theme_text_color='Custom',
            text_color=COLORS['text_secondary'],
            font_style='Caption'
        )
        url_card.add_widget(self.playlist_info_label)
        
        content.add_widget(url_card)
        
        # ====== بطاقة الفيديوهات ======
        videos_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            adaptive_height=True,
            md_bg_color=COLORS['card'],
            radius=[10, 10, 10, 10],
            padding=10,
            spacing=10
        )
        
        videos_header = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height='40dp',
            spacing=10
        )
        
        videos_label = MDLabel(
            text='الفيديوهات',
            font_style='H6',
            theme_text_color='Custom',
            text_color=COLORS['text'],
            halign='left'
        )
        videos_header.add_widget(videos_label)
        
        select_all_btn = MDFlatButton(
            text='تحديد الكل',
            text_color=COLORS['primary'],
            on_release=lambda x: self.select_all_videos(True)
        )
        videos_header.add_widget(select_all_btn)
        
        deselect_all_btn = MDFlatButton(
            text='إلغاء الكل',
            text_color=COLORS['primary'],
            on_release=lambda x: self.select_all_videos(False)
        )
        videos_header.add_widget(deselect_all_btn)
        
        videos_card.add_widget(videos_header)
        
        # قائمة الفيديوهات القابلة للتمرير
        self.videos_list = MDList(
            size_hint_y=None,
            adaptive_height=True
        )
        self.videos_list.md_bg_color = COLORS['bg']
        
        # قائمة فارغة
        self.empty_list_label = MDLabel(
            text='لا توجد فيديوهات\nاضغط على "جلب الفيديوهات" أولاً',
            halign='center',
            theme_text_color='Custom',
            text_color=COLORS['text_secondary'],
            font_style='Caption'
        )
        self.videos_list.add_widget(self.empty_list_label)
        
        videos_card.add_widget(self.videos_list)
        content.add_widget(videos_card)
        
        # ====== بطاقة الحجم التقديري ======
        size_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            adaptive_height=True,
            md_bg_color=COLORS['card'],
            radius=[10, 10, 10, 10],
            padding=10,
            spacing=10
        )
        
        size_label = MDLabel(
            text='الحجم التقديري',
            font_style='H6',
            theme_text_color='Custom',
            text_color=COLORS['text'],
            halign='center'
        )
        size_card.add_widget(size_label)
        
        # حاوية الأحجام
        self.size_grid = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            adaptive_height=True,
            spacing=5
        )
        
        # إنشاء صفوف الأحجام لكل جودة
        self.size_labels = {}
        for q in QUALITY_VALUES:
            row = MDBoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height='30dp',
                spacing=10
            )
            
            q_label = MDLabel(
                text=q,
                theme_text_color='Custom',
                text_color=COLORS['text_secondary'],
                halign='right',
                font_style='Caption'
            )
            row.add_widget(q_label)
            
            size_value = MDLabel(
                text='—',
                theme_text_color='Custom',
                text_color=COLORS['text'],
                halign='left',
                font_style='Caption',
                bold=True
            )
            row.add_widget(size_value)
            
            self.size_grid.add_widget(row)
            self.size_labels[q] = size_value
        
        size_card.add_widget(self.size_grid)
        
        self.size_note = MDLabel(
            text='',
            theme_text_color='Custom',
            text_color=COLORS['text_secondary'],
            font_style='Caption',
            halign='center'
        )
        size_card.add_widget(self.size_note)
        
        content.add_widget(size_card)
        
        # ====== بطاقة الإعدادات ======
        settings_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            adaptive_height=True,
            md_bg_color=COLORS['card'],
            radius=[10, 10, 10, 10],
            padding=10,
            spacing=10
        )
        
        settings_label = MDLabel(
            text='الإعدادات',
            font_style='H6',
            theme_text_color='Custom',
            text_color=COLORS['text'],
            halign='center'
        )
        settings_card.add_widget(settings_label)
        
        # اختيار الجودة
        quality_row = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height='40dp',
            spacing=10
        )
        
        quality_label = MDLabel(
            text='الجودة:',
            theme_text_color='Custom',
            text_color=COLORS['text_secondary'],
            halign='right',
            size_hint_x=0.3
        )
        quality_row.add_widget(quality_label)
        
        self.quality_btn = MDRaisedButton(
            text='1080p',
            md_bg_color=COLORS['card'],
            text_color=COLORS['text'],
            size_hint_x=0.7,
            on_release=self.show_quality_menu
        )
        quality_row.add_widget(self.quality_btn)
        
        settings_card.add_widget(quality_row)
        
        # خيار الضغط
        zip_row = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height='40dp',
            spacing=10
        )
        
        self.zip_checkbox = MDCheckbox(
            size_hint_x=0.1,
            active=False,
            on_active=self.on_zip_toggle
        )
        zip_row.add_widget(self.zip_checkbox)
        
        zip_label = MDLabel(
            text='ضغط الفيديوهات في ملف ZIP',
            theme_text_color='Custom',
            text_color=COLORS['text'],
            halign='left'
        )
        zip_row.add_widget(zip_label)
        
        settings_card.add_widget(zip_row)
        
        content.add_widget(settings_card)
        
        # ====== بطاقة التقدم ======
        progress_card = MDCard(
            orientation='vertical',
            size_hint_y=None,
            adaptive_height=True,
            md_bg_color=COLORS['card'],
            radius=[10, 10, 10, 10],
            padding=10,
            spacing=10
        )
        
        self.status_label = MDLabel(
            text=self.status_text,
            theme_text_color='Custom',
            text_color=COLORS['text'],
            halign='center',
            font_style='Caption'
        )
        progress_card.add_widget(self.status_label)
        
        self.progress_bar = MDProgressBar(
            value=self.progress_value,
            color=COLORS['primary']
        )
        progress_card.add_widget(self.progress_bar)
        
        content.add_widget(progress_card)
        
        # ====== أزرار التحكم ======
        buttons_row = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height='56dp',
            spacing=10,
            padding=[0, 5, 0, 5]
        )
        
        self.download_btn = MDRaisedButton(
            text=self.download_btn_text,
            md_bg_color=COLORS['primary'],
            text_color='white',
            font_size='16sp',
            disabled=self.download_btn_disabled,
            on_release=self.start_download
        )
        buttons_row.add_widget(self.download_btn)
        
        self.pause_btn = MDRaisedButton(
            text='⏸',
            md_bg_color=COLORS['card'],
            text_color=COLORS['warning'],
            disabled=True,
            on_release=self.toggle_pause,
            size_hint_x=0.15
        )
        buttons_row.add_widget(self.pause_btn)
        
        self.stop_btn = MDRaisedButton(
            text='⏹',
            md_bg_color=COLORS['card'],
            text_color=COLORS['danger'],
            disabled=True,
            on_release=self.cancel_download,
            size_hint_x=0.15
        )
        buttons_row.add_widget(self.stop_btn)
        
        content.add_widget(buttons_row)
        
        # إضافة المحتوى إلى القائمة القابلة للتمرير
        scroll.add_widget(content)
        main_layout.add_widget(scroll)
        
        self.add_widget(main_layout)
    
    # ========================================================================
    # دوال إدارة الواجهة
    # ========================================================================
    
    @mainthread
    def update_status(self, text, color='white'):
        """تحديث نص الحالة"""
        self.status_text = text
        self.status_label.text = text
        self.status_label.text_color = color
    
    @mainthread
    def update_progress(self, value):
        """تحديث شريط التقدم"""
        self.progress_value = value
        self.progress_bar.value = value
    
    @mainthread
    def update_download_btn(self, text, disabled):
        """تحديث زر التحميل"""
        self.download_btn.text = text
        self.download_btn.disabled = disabled
        self.download_btn_text = text
        self.download_btn_disabled = disabled
    
    @mainthread
    def update_playlist_info(self, title, count):
        """تحديث معلومات القائمة"""
        self.playlist_info_label.text = f'🎵 {title} — {count} فيديو'
        self.playlist_info_label.text_color = COLORS['success']
    
    @mainthread
    def add_video_to_list(self, index, title, var):
        """إضافة فيديو إلى القائمة"""
        # إزالة رسالة القائمة الفارغة
        if self.empty_list_label.parent:
            self.videos_list.remove_widget(self.empty_list_label)
        
        # إنشاء عنصر القائمة
        item = OneLineIconListItem(
            size_hint_y=None,
            height='40dp'
        )
        
        checkbox = MDCheckbox(
            active=True,
            size_hint_x=0.1
        )
        checkbox.bind(active=var)
        item.add_widget(checkbox)
        
        label = MDLabel(
            text=f'{index:>3}. {title[:40]}',
            theme_text_color='Custom',
            text_color=COLORS['text'],
            font_style='Caption',
            halign='left'
        )
        item.add_widget(label)
        
        self.videos_list.add_widget(item)
        self.video_checkboxes[index] = var
    
    @mainthread
    def clear_video_list(self):
        """مسح قائمة الفيديوهات"""
        self.videos_list.clear_widgets()
        self.video_checkboxes.clear()
        self.video_estimates.clear()
        self.videos_list.add_widget(self.empty_list_label)
    
    @mainthread
    def update_size_breakdown(self):
        """تحديث جدول الأحجام التقديرية"""
        selected = self.get_selected_videos()
        
        for q in QUALITY_VALUES:
            total_bytes = sum(
                self.video_estimates.get(video['url'], {}).get(q, 0)
                for video in selected
            )
            label = self.size_labels.get(q)
            if label:
                text = format_bytes(total_bytes) if total_bytes else '—'
                if q == self.quality:
                    text += ' ✓'
                label.text = text
                label.text_color = COLORS['success'] if q == self.quality else COLORS['text']
    
    @mainthread
    def show_snackbar(self, text, duration=3):
        """عرض إشعار"""
        Snackbar(text=text, duration=duration).open()
    
    @mainthread
    def show_dialog(self, title, text, buttons=None):
        """عرض حوار"""
        if not buttons:
            buttons = [MDFlatButton(text='موافق', on_release=lambda x: self.dialog.dismiss())]
        
        self.dialog = MDDialog(
            title=title,
            text=text,
            buttons=buttons
        )
        self.dialog.open()
    
    # ========================================================================
    # دوال قائمة التشغيل
    # ========================================================================
    
    def fetch_playlist(self, *args):
        """جلب قائمة التشغيل"""
        url = self.url_input.text.strip()
        if not url:
            self.show_snackbar('يرجى إدخال رابط قائمة التشغيل')
            return
        
        self.fetch_btn.disabled = True
        self.clear_video_list()
        self.update_status('جاري جلب الفيديوهات...', COLORS['warning'])
        self.playlist_info_label.text = 'جاري التحميل...'
        
        threading.Thread(target=self._fetch_playlist_thread, args=(url,), daemon=True).start()
    
    def _fetch_playlist_thread(self, url):
        """جلب القائمة في ثريد منفصل"""
        try:
            import yt_dlp
            
            opts = {
                'extract_flat': True,
                'quiet': True,
                'skip_download': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            title = info.get('title', 'قائمة تشغيل')
            entries = list(info.get('entries') or [info])
            
            self.playlist_entries = []
            for i, e in enumerate(entries, start=1):
                if not e:
                    continue
                vid = e.get('id') or e.get('url')
                self.playlist_entries.append({
                    'index': i,
                    'id': vid,
                    'title': e.get('title') or f'فيديو {i}',
                    'url': f'https://www.youtube.com/watch?v={vid}',
                    'selected': True
                })
            
            # تحديث الواجهة
            self.update_playlist_info(title, len(self.playlist_entries))
            
            # إضافة الفيديوهات للقائمة
            for entry in self.playlist_entries:
                var = BooleanProperty(True)
                self.add_video_to_list(entry['index'], entry['title'], var)
                entry['selected_var'] = var
            
            self.update_download_btn('⬇ تحميل', False)
            self.update_status('جاهز للتحميل', 'white')
            
            # بدأ تقدير الأحجام
            threading.Thread(target=self._estimate_sizes_thread, daemon=True).start()
            
        except Exception as e:
            self.update_status('خطأ في جلب القائمة', COLORS['danger'])
            self.show_dialog('خطأ', f'تعذر جلب القائمة:\n{str(e)}')
        
        finally:
            self.fetch_btn.disabled = False
    
    def _estimate_sizes_thread(self):
        """تقدير أحجام الفيديوهات في ثريد منفصل"""
        self.estimation_in_progress = True
        self.update_status('جاري حساب الأحجام التقديرية...', COLORS['warning'])
        
        try:
            import yt_dlp
            opts = {'quiet': True, 'skip_download': True, 'no_warnings': True}
            
            total = len(self.playlist_entries)
            for i, entry in enumerate(self.playlist_entries, start=1):
                self.update_status(f'تقدير الحجم: فيديو {i} من {total}', COLORS['warning'])
                
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(entry['url'], download=False)
                    
                    estimates = {}
                    for q in QUALITY_VALUES:
                        estimates[q] = self._estimate_video_size(info, q)
                    
                    self.video_estimates[entry['url']] = estimates
                    
                except Exception:
                    self.video_estimates[entry['url']] = {}
                
                # تحديث الأحجام
                self.update_size_breakdown()
            
            self.estimation_in_progress = False
            self.update_status('جاهز للتحميل', 'white')
            
        except Exception as e:
            self.update_status('خطأ في تقدير الأحجام', COLORS['danger'])
    
    def _estimate_video_size(self, info, quality_label):
        """تقدير حجم الفيديو"""
        duration = info.get('duration') or 0
        formats = info.get('formats') or []
        
        def fmt_size(f):
            size = f.get('filesize') or f.get('filesize_approx')
            if size:
                return size
            tbr = f.get('tbr')
            if tbr and duration:
                return int(tbr * 1000 / 8 * duration)
            return 0
        
        if quality_label == "صوت فقط (MP3)":
            audio_formats = [
                f for f in formats
                if f.get('vcodec') in (None, 'none') and f.get('acodec') not in (None, 'none')
            ]
            if not audio_formats:
                return 0
            best_audio = max(audio_formats, key=lambda f: f.get('abr') or 0)
            return fmt_size(best_audio)
        
        height_limit = QUALITY_TO_HEIGHT.get(quality_label)
        video_formats = [f for f in formats if f.get('vcodec') not in (None, 'none')]
        if height_limit:
            limited = [f for f in video_formats if (f.get('height') or 0) <= height_limit]
            if limited:
                video_formats = limited
        if not video_formats:
            return 0
        
        best_video = max(video_formats, key=lambda f: ((f.get('height') or 0), (f.get('tbr') or 0)))
        video_size = fmt_size(best_video)
        
        if best_video.get('acodec') not in (None, 'none'):
            return video_size
        
        audio_formats = [
            f for f in formats
            if f.get('vcodec') in (None, 'none') and f.get('acodec') not in (None, 'none')
        ]
        audio_size = fmt_size(max(audio_formats, key=lambda f: f.get('abr') or 0)) if audio_formats else 0
        return video_size + audio_size
    
    # ========================================================================
    # دوال الاختيار والتحكم
    # ========================================================================
    
    def get_selected_videos(self):
        """الحصول على الفيديوهات المحددة"""
        selected = []
        for entry in self.playlist_entries:
            if entry.get('selected_var', BooleanProperty(False)).get():
                selected.append(entry)
        return selected
    
    def select_all_videos(self, select):
        """تحديد أو إلغاء تحديد الكل"""
        for entry in self.playlist_entries:
            if 'selected_var' in entry:
                entry['selected_var'].set(select)
        self.update_size_breakdown()
    
    def on_zip_toggle(self, checkbox, value):
        """تفعيل/إلغاء وضع الضغط"""
        self.zip_mode = value
    
    def show_quality_menu(self, *args):
        """عرض قائمة اختيار الجودة"""
        menu_items = []
        for q in QUALITY_VALUES:
            menu_items.append({
                'text': q,
                'on_release': lambda x=q: self.set_quality(x)
            })
        
        self.quality_menu = MDDropdownMenu(
            caller=self.quality_btn,
            items=menu_items,
            position='center',
            width_mult=4
        )
        self.quality_menu.open()
    
    def set_quality(self, quality):
        """تعيين الجودة المختارة"""
        self.quality = quality
        self.quality_btn.text = quality
        if self.quality_menu:
            self.quality_menu.dismiss()
        self.update_size_breakdown()
    
    def paste_from_clipboard(self, *args):
        """لصق من الحافظة"""
        try:
            from kivy.core.clipboard import Clipboard
            text = Clipboard.paste()
            if text:
                self.url_input.text = text
        except:
            pass
    
    def clear_all(self):
        """مسح كل شيء"""
        self.playlist_entries = []
        self.video_checkboxes.clear()
        self.video_estimates.clear()
        self.clear_video_list()
        self.playlist_info_label.text = ''
        self.update_download_btn('⬇ تحميل', True)
        self.update_status('جاهز للتحميل', 'white')
        for label in self.size_labels.values():
            label.text = '—'
    
    def show_menu(self):
        """عرض القائمة الجانبية"""
        self.show_dialog('معلومات', 
            'مُحمّل قوائم تشغيل يوتيوب\n'
            'الإصدار 2.0\n\n'
            'ميزات التطبيق:\n'
            '• تحميل قوائم تشغيل كاملة\n'
            '• اختيار الجودة (1080p, 720p, ...)\n'
            '• تقدير حجم التحميل\n'
            '• إيقاف مؤقت واستئناف\n'
            '• ضغط الملفات في ZIP\n'
            '• واجهة عربية بالكامل'
        )
    
    # ========================================================================
    # دوال ffmpeg
    # ========================================================================
    
    def _prepare_ffmpeg(self):
        """تجهيز ffmpeg"""
        try:
            # محاولة استخدام ffmpeg المدمج
            if platform == 'android':
                # على الأندرويد، نحاول استخدام ffmpeg من النظام
                import subprocess
                try:
                    subprocess.run(['ffmpeg', '-version'], capture_output=True)
                    self.ffmpeg_ready = True
                    self.update_status('جاهز للتحميل', 'white')
                    return
                except:
                    pass
            
            # استخدام static_ffmpeg
            try:
                import static_ffmpeg
                static_ffmpeg.add_paths()
                self.ffmpeg_ready = True
                self.update_status('جاهز للتحميل', 'white')
            except:
                # تنبيه المستخدم
                self.update_status('ffmpeg غير متوفر، قد لا تعمل بعض الميزات', COLORS['warning'])
                self.ffmpeg_ready = True  # نستمر مع yt-dlp بدون ffmpeg
                
        except Exception as e:
            self.update_status('خطأ في تجهيز ffmpeg', COLORS['danger'])
            self.ffmpeg_ready = True  # نستمر مع yt-dlp بدون ffmpeg
    
    # ========================================================================
    # دوال التحميل
    # ========================================================================
    
    def start_download(self, *args):
        """بدء التحميل"""
        selected = self.get_selected_videos()
        if not selected:
            self.show_snackbar('يرجى تحديد فيديو واحد على الأقل')
            return
        
        self.is_downloading = True
        self.cancel_event.clear()
        self.pause_event.set()
        self.videos_done = 0
        self.total_selected = len(selected)
        self.failed_videos = []
        self.completed_bytes = 0
        
        self.update_download_btn('⏳ جاري التحميل...', True)
        self.pause_btn.disabled = False
        self.stop_btn.disabled = False
        self.pause_btn.text = '⏸'
        self.is_paused = False
        
        threading.Thread(target=self._download_thread, args=(selected,), daemon=True).start()
    
    def _download_thread(self, selected_entries):
        """ثريد التحميل الرئيسي"""
        try:
            import yt_dlp
            
            # تحديد مسار الحفظ
            if platform == 'android':
                download_dir = get_download_path()
            else:
                download_dir = get_download_path()
            
            temp_dir = os.path.join(download_dir, 'temp_download')
            os.makedirs(temp_dir, exist_ok=True)
            
            quality = self.quality
            playlist_title = sanitize_filename(f'playlist_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            
            for entry in selected_entries:
                if self.cancel_event.is_set():
                    break
                
                # التحقق من الإيقاف المؤقت
                while not self.pause_event.is_set():
                    if self.cancel_event.is_set():
                        break
                    time.sleep(0.2)
                if self.cancel_event.is_set():
                    break
                
                # تخطي الفيديو الموجود مسبقاً
                if self._video_exists(temp_dir, entry['index']):
                    self.videos_done += 1
                    self.update_progress(self.videos_done / max(self.total_selected, 1))
                    continue
                
                # إعدادات التحميل
                format_str = self._get_format_string(quality)
                outtmpl = os.path.join(temp_dir, f"{entry['index']:03d} - %(title)s.%(ext)s")
                
                ydl_opts = {
                    'format': format_str,
                    'outtmpl': outtmpl,
                    'progress_hooks': [
                        lambda d, idx=entry['index'], t=entry['title']: 
                        self._progress_hook(d, idx, t)
                    ],
                    'merge_output_format': 'mp4',
                    'noplaylist': True,
                    'quiet': True,
                    'no_warnings': True,
                }
                
                if quality == "صوت فقط (MP3)":
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([entry['url']])
                except DownloadCancelled:
                    break
                except Exception as e:
                    self.failed_videos.append((entry['index'], entry['title'], str(e)))
                
                self.videos_done += 1
                self.update_progress(self.videos_done / max(self.total_selected, 1))
            
            # إنهاء التحميل
            if self.cancel_event.is_set():
                self.update_status('تم إلغاء التحميل', COLORS['danger'])
                self.update_progress(0)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                return
            
            # إنهاء وتنظيم الملفات
            self._finalize_download(temp_dir, download_dir, playlist_title)
            
        except Exception as e:
            self.show_dialog('خطأ', f'حدث خطأ أثناء التحميل:\n{str(e)}')
            self.update_status('حدث خطأ!', COLORS['danger'])
        
        finally:
            self.is_downloading = False
            self.update_download_btn('⬇ تحميل', False)
            self.pause_btn.disabled = True            self.stop_btn.disabled = True
    
    def _get_format_string(self, quality):
        """الحصول على صيغة التحميل المناسبة"""
        mapping = {
            "أعلى جودة (Best)": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
            "صوت فقط (MP3)": "bestaudio/best",
        }
        return mapping.get(quality, "best")
    
    def _progress_hook(self, d, video_index, video_title):
        """تحديث التقدم أثناء التحميل"""
        if self.cancel_event.is_set():
            raise DownloadCancelled("تم إلغاء التحميل")
        
        while not self.pause_event.is_set():
            if self.cancel_event.is_set():
                raise DownloadCancelled("تم إلغاء التحميل")
            time.sleep(0.2)
        
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').strip()
            speed = d.get('speed', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            speed_text = f"{format_bytes(speed)}/s" if speed else "..."
            short_title = (video_title[:25] + '…') if len(video_title) > 25 else video_title
            
            self.update_status(
                f'فيديو {video_index}/{self.total_selected} ({short_title}) — {percent} • {speed_text}',
                'white'
            )
            
            try:
                current_fraction = float(percent.replace('%', '')) / 100
            except:
                current_fraction = 0
            overall = (self.videos_done + current_fraction) / max(self.total_selected, 1)
            self.update_progress(min(overall, 1.0))
            
        elif d['status'] == 'finished':
            self.update_status(f'فيديو {video_index}/{self.total_selected} — جاري المعالجة...', 'white')
    
    def _video_exists(self, folder, index):
        """التحقق من وجود فيديو مكتمل"""
        pattern = os.path.join(folder, f"{index:03d} - *")
        for path in glob.glob(pattern):
            if not path.endswith(('.part', '.ytdl', '.temp')):
                return True
        return False
    
    def _finalize_download(self, temp_dir, save_dir, playlist_title):
        """إنهاء التحميل وترتيب الملفات"""
        if self.zip_mode:
            self.update_status('جاري ضغط الملفات...', COLORS['warning'])
            zip_path = os.path.join(save_dir, f'{playlist_title}.zip')
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), arcname=file)
            
            shutil.rmtree(temp_dir, ignore_errors=True)
            total_size = format_bytes(os.path.getsize(zip_path))
            self.last_output_path = zip_path
            self.show_dialog('اكتمل التحميل', 
                f'تم تحميل وضغط الفيديوهات بنجاح!\n'
                f'الحجم الكلي: {total_size}\n'
                f'الموقع: {zip_path}'
            )
            
        else:
            final_dir = os.path.join(save_dir, playlist_title)
            if os.path.exists(final_dir):
                shutil.rmtree(final_dir)
            shutil.move(temp_dir, final_dir)
            total_size = format_bytes(get_folder_size(final_dir))
            self.last_output_path = final_dir
            self.show_dialog('اكتمل التحميل',
                f'تم تحميل الفيديوهات بنجاح!\n'
                f'الحجم الكلي: {total_size}\n'
                f'الموقع: {final_dir}'
            )
        
        self.update_status('تم التحميل بنجاح! 🎉', COLORS['success'])
        self.update_progress(1)
    
    def toggle_pause(self, *args):
        """إيقاف مؤقت/استئناف"""
        if not self.is_downloading:
            return
        
        if self.is_paused:
            self.pause_event.set()
            self.is_paused = False
            self.pause_btn.text = '⏸'
            self.update_status('جاري استئناف التحميل...', 'white')
        else:
            self.pause_event.clear()
            self.is_paused = True
            self.pause_btn.text = '▶'
            self.update_status('تم إيقاف التحميل مؤقتاً', COLORS['warning'])
    
    def cancel_download(self, *args):
        """إلغاء التحميل"""
        if self.is_downloading:
            self.cancel_event.set()
            self.pause_event.set()
            self.update_status('جاري إلغاء التحميل...', COLORS['danger'])
            self.stop_btn.disabled = True

# ============================================================================
# دوال مساعدة إضافية
# ============================================================================

def get_folder_size(path: str) -> int:
    """حساب حجم المجلد"""
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except:
                pass
    return total

# ============================================================================
# تطبيق Kivy الرئيسي
# ============================================================================

class YouTubeDownloaderApp(MDApp):
    """التطبيق الرئيسي"""
    
    def build(self):
        """بناء التطبيق"""
        self.theme_cls.primary_palette = 'Red'
        self.theme_cls.theme_style = 'Dark'
        self.theme_cls.primary_hue = '700'
        
        # تعيين الخط العربي
        self.set_arabic_font()
        
        # إنشاء وإرجاع الشاشة الرئيسية
        return MainScreen()
    
    def set_arabic_font(self):
        """تعيين الخط العربي"""
        try:
            from kivy.core.text import LabelBase
            # محاولة استخدام خط يدعم العربية
            LabelBase.register(name='Arabic', fn_regular='DejaVuSans.ttf')
        except:
            pass
    
    def on_start(self):
        """عند بدء التطبيق"""
        # طلب الصلاحيات للأندرويد
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.INTERNET
                ])
            except:
                pass
    
    def on_stop(self):
        """عند إيقاف التطبيق"""
        pass

# ============================================================================
# تشغيل التطبيق
# ============================================================================

if __name__ == '__main__':
    YouTubeDownloaderApp().run()
