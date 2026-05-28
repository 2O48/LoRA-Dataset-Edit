"""
视觉数据集标注查看器 v7
- 双图 / 三图模式
- Tag 气泡编辑 + 全局Tag统计
- 批量操作 / 删除图片(含配套文件) / 快捷键
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import re, threading, os, subprocess, queue, time, sys, send2trash
from pathlib import Path
from collections import Counter
from PIL import Image, ImageTk

# ── 尝试导入 send2trash，没有就用永久删除 ──────────────
try:
    import send2trash
    def _trash(path):
        send2trash.send2trash(str(path))
except ImportError:
    send2trash = None
    def _trash(path):
        os.remove(path)

IMAGE_EXTS = {'.jpg','.jpeg','.png','.gif','.webp','.bmp','.tiff','.avif'}

# ── 颜色 ──────────────────────────────────────────────
BG       = '#111113'
SURFACE  = '#1a1a1f'
SURFACE2 = '#222228'
SURFACE3 = '#2a2a34'
BORDER   = '#333340'
ACCENT   = '#6868ff'
ACCENT_H = '#8888ff'
TEXT     = '#ebebf5'
TEXT_DIM = '#8080a0'
TEXT_MUT = '#44445a'
GREEN    = '#46d47e'
YELLOW   = '#f5c842'
ORANGE   = '#f58c30'
RED      = '#e84444'
RED_H    = '#ff6060'
TAG_BG   = '#1e1e32'
TAG_BDR  = '#303050'
TAG_FG   = '#9999cc'
TAG_X    = '#cc4444'

def F(sz=10, bold=False, mono=False):
    fam = 'Consolas' if mono else '微软雅黑'
    return (fam, sz, 'bold' if bold else 'normal')

THUMB_W, THUMB_H = 100, 62


# ══════════════════════════════════════════════════════
# Tag 气泡
# ══════════════════════════════════════════════════════

class TagBubble(tk.Frame):
    def __init__(self, master, tag, on_del, on_ren, **kw):
        super().__init__(master, bg=TAG_BG, cursor='hand2',
                         highlightthickness=1, highlightbackground=TAG_BDR, **kw)
        self.tag = tag
        self._lbl = tk.Label(self, text=tag, bg=TAG_BG, fg=TAG_FG,
                              font=F(10, mono=True), padx=6, pady=2)
        self._lbl.pack(side='left')
        self._x = tk.Label(self, text='×', bg=TAG_BG, fg=TAG_X,
                            font=F(11, mono=True), padx=4, pady=2, cursor='hand2')
        self._x.pack(side='left')
        for w in (self, self._lbl, self._x):
            w.bind('<Enter>', self._on); w.bind('<Leave>', self._off)
        self._x.bind('<Button-1>', lambda e: on_del(tag))
        self._lbl.bind('<Double-Button-1>', lambda e: on_ren(tag))

    def _on(self, e):
        for w in (self, self._lbl, self._x): w.config(bg=SURFACE3)
        self.config(highlightbackground=ACCENT)

    def _off(self, e):
        for w in (self, self._lbl, self._x): w.config(bg=TAG_BG)
        self.config(highlightbackground=TAG_BDR)


class TagPanel(tk.Frame):
    """气泡式 Tag 编辑器"""
    def __init__(self, master, on_change, **kw):
        super().__init__(master, bg=SURFACE2, **kw)
        self.on_change = on_change
        self._tags = []
        self._build()

    def _build(self):
        self._cv = tk.Canvas(self, bg=SURFACE2, highlightthickness=0)
        self._cv.pack(fill='both', expand=True, side='top')
        self._inner = tk.Frame(self._cv, bg=SURFACE2)
        self._win = self._cv.create_window(0, 0, anchor='nw', window=self._inner)
        vsb = tk.Scrollbar(self, orient='vertical', command=self._cv.yview,
                           bg=SURFACE2, troughcolor=SURFACE2, relief='flat', bd=0, width=5)
        vsb.pack(side='right', fill='y')
        self._cv.config(yscrollcommand=vsb.set)
        self._inner.bind('<Configure>', self._sync)
        self._cv.bind('<Configure>', lambda e: (
            self._cv.itemconfig(self._win, width=e.width), self._relayout()))
        for w in (self._cv, self._inner):
            w.bind('<MouseWheel>', self._scroll)
            w.bind('<Button-4>',   self._scroll)
            w.bind('<Button-5>',   self._scroll)
        # 输入栏
        bar = tk.Frame(self, bg=SURFACE2, pady=5)
        bar.pack(fill='x', side='bottom', padx=6)
        tk.Frame(self, bg=BORDER, height=1).pack(fill='x', side='bottom')
        tk.Label(bar, text='＋', bg=SURFACE2, fg=ACCENT,
                 font=F(12, bold=True)).pack(side='left', padx=(2,5))
        self._iv = tk.StringVar()
        self._ie = tk.Entry(bar, textvariable=self._iv, bg=SURFACE3, fg=TEXT,
                             insertbackground=ACCENT, relief='flat', bd=0,
                             font=F(10, mono=True),
                             highlightthickness=1, highlightbackground=BORDER)
        self._ie.pack(side='left', fill='x', expand=True, ipady=4)
        self._ie.bind('<Return>',   self._commit)
        self._ie.bind('<Tab>',      self._commit)
        self._ie.bind('<KP_Enter>', self._commit)
        tk.Label(bar, text='回车确认', bg=SURFACE2, fg=TEXT_MUT,
                 font=F(9)).pack(side='left', padx=6)

    def _sync(self, e=None):
        self._cv.config(scrollregion=self._cv.bbox('all'))
        self._cv.itemconfig(self._win, width=self._cv.winfo_width())

    def _scroll(self, e):
        d = e.delta if hasattr(e,'delta') and e.delta else (-120 if e.num==5 else 120)
        self._cv.yview_scroll(-1 if d > 0 else 1, 'units')

    def set_tags(self, tags):
        self._tags = list(tags); self._relayout()

    def get_tags(self): return list(self._tags)

    def _relayout(self):
        for w in self._inner.winfo_children(): w.destroy()
        wrap = max(self._cv.winfo_width() - 14, 260)
        row = tk.Frame(self._inner, bg=SURFACE2)
        row.pack(anchor='w', padx=6, pady=5)
        rw = 0
        for tag in self._tags:
            b = TagBubble(row, tag, self._del, self._ren)
            b.pack(side='left', padx=3, pady=2)
            b.update_idletasks()
            bw = b.winfo_reqwidth() + 6
            rw += bw
            if rw > wrap:
                row = tk.Frame(self._inner, bg=SURFACE2)
                row.pack(anchor='w', padx=6)
                b.pack_forget()
                b = TagBubble(row, tag, self._del, self._ren)
                b.pack(side='left', padx=3, pady=2)
                rw = bw
        self._inner.update_idletasks()
        self._cv.config(scrollregion=self._cv.bbox('all'))

    def _commit(self, e):
        new = [t.strip() for t in self._iv.get().split(',') if t.strip()]
        ch = False
        for t in new:
            if t not in self._tags: self._tags.append(t); ch = True
        self._iv.set('')
        if ch: self._relayout(); self.on_change(self._tags)
        return 'break'

    def _del(self, tag):
        if tag in self._tags:
            self._tags.remove(tag); self._relayout(); self.on_change(self._tags)

    def _ren(self, old):
        nw = simpledialog.askstring('重命名 Tag', f'当前：{old}\n新名称：',
                                     initialvalue=old, parent=self.winfo_toplevel())
        if nw and nw.strip() and nw.strip() != old:
            i = self._tags.index(old); self._tags[i] = nw.strip()
            self._relayout(); self.on_change(self._tags)

    def add_tag(self, tag):
        if tag not in self._tags:
            self._tags.append(tag); self._relayout(); self.on_change(self._tags)

    def focus_input(self): self._ie.focus_set()


# ══════════════════════════════════════════════════════
# 全局 Tag 面板
# ══════════════════════════════════════════════════════

class GlobalTagPanel(tk.Frame):
    def __init__(self, master, on_add, on_filter, **kw):
        super().__init__(master, bg=SURFACE, **kw)
        self.on_add    = on_add
        self.on_filter = on_filter   # callback(tag_str or None)
        self._all      = []
        self._filter_tag = None      # 当前筛选的tag
        self._click_job  = None
        self._click_idx  = -1
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=SURFACE, pady=7)
        hdr.pack(fill='x', padx=10)
        tk.Label(hdr, text='全局 Tags', bg=SURFACE, fg=TEXT_DIM,
                 font=F(10, bold=True)).pack(side='left')
        self._lc = tk.Label(hdr, text='', bg=SURFACE, fg=TEXT_MUT, font=F(9))
        self._lc.pack(side='right')
        tk.Button(hdr, text='🌐', command=self._translate_visible,
                  bg=SURFACE, fg=TEXT_DIM, relief='flat', font=F(9),
                  cursor='hand2', activebackground=SURFACE2,
                  bd=0, padx=4).pack(side='right', padx=2)

        # 搜索框
        sf = tk.Frame(self, bg=SURFACE, pady=3)
        sf.pack(fill='x', padx=6)
        self._sv = tk.StringVar()
        tk.Entry(sf, textvariable=self._sv, bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief='flat', bd=0,
                 font=F(10, mono=True), highlightthickness=1,
                 highlightbackground=BORDER
                 ).pack(fill='x', ipady=4)
        self._sv.trace_add('write', lambda *a: self._render())

        # 筛选状态栏
        self._fbar = tk.Frame(self, bg=SURFACE2, pady=3)
        self._fbar.pack(fill='x', padx=6)
        self._flbl = tk.Label(self._fbar, text='', bg=SURFACE2, fg=ACCENT,
                               font=F(9, mono=True))
        self._flbl.pack(side='left', padx=4)
        self._fclear = tk.Button(self._fbar, text='× 清除筛选', bg=SURFACE2, fg=TEXT_MUT,
                                  relief='flat', bd=0, font=F(9), cursor='hand2',
                                  command=self._clear_filter)
        # 初始隐藏
        self._fbar.pack_forget()

        tk.Frame(self, bg=BORDER, height=1).pack(fill='x')

        lf = tk.Frame(self, bg=SURFACE)
        lf.pack(fill='both', expand=True)
        sb = tk.Scrollbar(lf, bg=SURFACE, troughcolor=SURFACE,
                          relief='flat', bd=0, width=5)
        sb.pack(side='right', fill='y')
        # 中文翻译列
        self._lb_zh = tk.Listbox(lf, bg=SURFACE, fg=TEXT_MUT,
                                  selectbackground=SURFACE3, selectforeground=TEXT,
                                  activestyle='none', relief='flat', bd=0,
                                  font=F(10), highlightthickness=0,
                                  exportselection=False, width=12,
                                  yscrollcommand=lambda *a: None)
        self._lb_zh.pack(side='right', fill='y')

        # 可拖动分隔条（调整中文列宽）
        _sash = tk.Frame(lf, bg=BORDER, width=4, cursor='sb_h_double_arrow')
        _sash.pack(side='right', fill='y')
        def _sash_drag(e):
            root_x = e.x_root
            lb_zh_x = self._lb_zh.winfo_rootx()
            lb_zh_w = self._lb_zh.winfo_width()
            new_w = lb_zh_x + lb_zh_w - root_x
            char_w = self._lb_zh.winfo_width() / max(self._lb_zh.cget('width'), 1)
            new_chars = max(4, int(new_w / max(char_w, 6)))
            self._lb_zh.config(width=new_chars)
        _sash.bind('<B1-Motion>', _sash_drag)

        self._lb = tk.Listbox(lf, bg=SURFACE, fg=TAG_FG,
                               selectbackground=SURFACE3, selectforeground=TEXT,
                               activestyle='none', relief='flat', bd=0,
                               font=F(10, mono=True), yscrollcommand=sb.set,
                               highlightthickness=0, exportselection=False,
                               cursor='hand2')
        self._lb.pack(side='left', fill='both', expand=True)

        def _sync_scroll(*args):
            self._lb.yview(*args)
            self._lb_zh.yview(*args)
        sb.config(command=_sync_scroll)

        def _on_lb_scroll(first, last):
            sb.set(first, last)
            self._lb_zh.yview_moveto(first)
        self._lb.config(yscrollcommand=_on_lb_scroll)

        def _on_zh_scroll(first, last):
            sb.set(first, last)
            self._lb.yview_moveto(first)
        self._lb_zh.config(yscrollcommand=_on_zh_scroll)

        # 用延迟区分单击/双击，避免双击时触发两次单击逻辑
        self._click_job  = None
        self._click_idx  = -1
        self._lb.bind('<Button-1>',        self._on_lb_click)
        self._lb.bind('<Double-Button-1>', self._on_lb_dbl)
        self._lb_zh.bind('<Button-1>',        self._on_lb_click)
        self._lb_zh.bind('<Double-Button-1>', self._on_lb_dbl)
        for w in (self._lb, self._lb_zh):
            w.bind('<MouseWheel>', lambda e: (self._lb.yview_scroll(int(-e.delta/120), 'units'),
                                              self._lb_zh.yview_scroll(int(-e.delta/120), 'units')) or 'break')

        tip = tk.Frame(self, bg=SURFACE, pady=4)
        tip.pack(fill='x')
        tk.Label(tip, text='单击筛选 · 再点取消 · 双击添加到当前图',
                 bg=SURFACE, fg=TEXT_MUT, font=F(9), padx=8).pack(side='left')

    def update_tags(self, counter):
        self._all = sorted(counter.items(), key=lambda x: -x[1])
        self._lc.config(text=f'{len(self._all)} 种')
        self._zh_cache = getattr(self, '_zh_cache', {})
        self._render()

    def _render(self):
        flt = self._sv.get().strip().lower()
        self._lb.delete(0, 'end')
        self._lb_zh.delete(0, 'end')
        self._visible_tags = []
        zh = getattr(self, '_zh_cache', {})
        for tag, cnt in self._all:
            if flt and flt not in tag.lower(): continue
            self._lb.insert('end', f'{cnt:>4}  {tag}')
            self._lb_zh.insert('end', zh.get(tag, ''))
            self._visible_tags.append(tag)
        if self._filter_tag:
            self._highlight_filter_tag()

    def _get_tag(self, idx):
        line = self._lb.get(idx).strip()
        return line.split(None, 1)[-1] if ' ' in line else line

    def _on_lb_click(self, e):
        """单击：等 220ms，如果没有双击再触发筛选"""
        idx = self._lb.nearest(e.y)
        if idx < 0: return
        self._click_idx = idx
        if self._click_job:
            self._lb.after_cancel(self._click_job)
        self._click_job = self._lb.after(220, lambda: self._do_filter(idx))

    def _on_lb_dbl(self, e):
        """双击：取消单击计时，执行添加"""
        if self._click_job:
            self._lb.after_cancel(self._click_job)
            self._click_job = None
        idx = self._lb.nearest(e.y)
        if idx < 0: return
        self.on_add(self._get_tag(idx))

    def _do_filter(self, idx):
        """单击防抖后真正执行筛选/取消"""
        self._click_job = None
        if idx >= self._lb.size(): return
        tag = self._get_tag(idx)
        if self._filter_tag == tag:
            self._clear_filter()
        else:
            self._filter_tag = tag
            self._flbl.config(text=f'筛选：{tag}')
            self._fclear.pack(side='right', padx=4)
            self._fbar.pack(fill='x', padx=6)
            self._highlight_filter_tag()
            self.on_filter(tag)

    def _clear_filter(self):
        self._filter_tag = None
        self._fbar.pack_forget()
        self._render()
        self.on_filter(None)

    def _highlight_filter_tag(self):
        for i in range(self._lb.size()):
            tag = self._get_tag(i)
            if tag == self._filter_tag:
                self._lb.itemconfig(i, fg=ACCENT, selectforeground=ACCENT)
            # 其他tag颜色由 highlight_current 处理

    def highlight_current(self, cur):
        for i in range(self._lb.size()):
            tag = self._get_tag(i)
            if tag == self._filter_tag:
                fg = ACCENT_H
            elif tag in cur:
                fg = GREEN
            else:
                fg = TAG_FG
            self._lb.itemconfig(i, fg=fg)

    def sync_filter(self, tag):
        """从外部（Tag搜索框）同步筛选状态"""
        if tag:
            self._filter_tag = tag
            self._flbl.config(text=f'筛选：{tag}')
            self._fclear.pack(side='right', padx=4)
            self._fbar.pack(fill='x', padx=6)
            self._highlight_filter_tag()
        else:
            self._filter_tag = None
            self._fbar.pack_forget()

    def _translate_visible(self):
        import urllib.request, urllib.parse, json, threading
        items = list(getattr(self, '_visible_tags', []))
        if not items:
            return
        # 只翻译没有缓存的
        zh = getattr(self, '_zh_cache', {})
        to_translate = [t for t in items if t not in zh]
        if not to_translate:
            return
        self._lc.config(text='翻译中...')

        def do_translate():
            batch = 60
            for i in range(0, len(to_translate), batch):
                chunk = to_translate[i:i + batch]
                text = '\n'.join(chunk)
                url = ('https://translate.googleapis.com/translate_a/single'
                       '?client=gtx&sl=auto&tl=zh-CN&dt=t&q='
                       + urllib.parse.quote(text))
                try:
                    req = urllib.request.Request(
                        url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read())
                    translated = ''.join(r[0] for r in data[0] if r[0])
                    parts = translated.split('\n')
                    for tag, tr in zip(chunk, parts):
                        zh[tag] = tr.strip()
                except Exception:
                    pass

            def update_ui():
                self._zh_cache = zh
                # 更新中文列
                visible = getattr(self, '_visible_tags', [])
                self._lb_zh.delete(0, 'end')
                for tag in visible:
                    self._lb_zh.insert('end', zh.get(tag, ''))
                self._lc.config(text=f'{len(self._all)} 种')

            self.after(0, update_ui)

        threading.Thread(target=do_translate, daemon=True).start()


# ══════════════════════════════════════════════════════
# 图片面板（异步加载，不阻塞 UI）
# ══════════════════════════════════════════════════════

class ImgPanel(tk.Frame):
    def __init__(self, master, label, color, on_zoom, show_resolution=False, on_size_known=None, **kw):
        super().__init__(master, bg=BG, **kw)
        self._show_res = show_resolution
        self._on_size_known = on_size_known  # callback(width, height)

        hdr = tk.Frame(self, bg=SURFACE, pady=6)
        hdr.pack(fill='x')
        tk.Label(hdr, text=label, bg=SURFACE, fg=color,
                 font=F(11, bold=True), padx=12).pack(side='left')
        tk.Label(hdr, text='点击放大', bg=SURFACE, fg=TEXT_MUT,
                 font=F(9), padx=6).pack(side='right')

        # 底部信息栏
        info_bar = tk.Frame(self, bg=SURFACE2)
        info_bar.pack(fill='x', side='bottom')
        self.fname = tk.Label(info_bar, text='—', bg=SURFACE2, fg=TEXT_MUT,
                               font=F(10), pady=4, padx=12, anchor='w')
        self.fname.pack(side='left', fill='x', expand=True)
        self.lbl_res = tk.Label(info_bar, text='', bg=SURFACE2, fg=ACCENT,
                                 font=F(10, mono=True), pady=4, padx=12)
        if self._show_res:
            self.lbl_res.pack(side='right')

        self.canvas = tk.Canvas(self, bg='#080810', highlightthickness=0, cursor='hand2')
        self.canvas.pack(fill='both', expand=True)

        self._pil      = None
        self._photo    = None
        self._cur_path = None
        self._resize_job = None

        self.canvas.bind('<Configure>', self._on_resize)
        self.canvas.bind('<Button-1>',  lambda e: on_zoom(self))

    # ── 外部调用：展示某路径 ──────────────────

    def show(self, path, pil_cache: dict):
        """异步展示图片，pil_cache 是 App 级别的 PIL 缓存字典"""
        self._cur_path = path
        self.fname.config(text=path.name if path else '—')
        self._pil = None
        self._draw_placeholder('正在加载…', TEXT_MUT)

        if not path or not path.exists():
            self.lbl_res.config(text='')
            self._draw_placeholder('⚠  无对应图片', ORANGE)
            return

        # 已缓存直接用
        if path in pil_cache:
            self._pil = pil_cache[path]
            self._update_res_label()
            self._draw()
            return

        # 后台线程读取
        target = path
        def _load():
            try:
                img = Image.open(target)
                img.load()          # 强制解码，在后台完成
                pil_cache[target] = img
            except Exception as ex:
                pil_cache[target] = ex   # 存异常占位
            # 回调到主线程
            self.after(0, lambda: self._on_loaded(target, pil_cache))

        threading.Thread(target=_load, daemon=True).start()

    def _on_loaded(self, path, pil_cache):
        if path != self._cur_path:
            return
        result = pil_cache.get(path)
        if isinstance(result, Exception):
            self._draw_placeholder(f'加载失败：{result}', RED)
        else:
            self._pil = result
            self._update_res_label()
            self._draw()

    def _update_res_label(self):
        if self._pil:
            iw, ih = self._pil.size
            if self._show_res:
                self.lbl_res.config(text=f'{iw} × {ih}')
            if self._on_size_known:
                self._on_size_known(iw, ih)
        else:
            self.lbl_res.config(text='')

    # ── 绘制 ─────────────────────────────────

    def _draw(self):
        if not self._pil:
            return
        c = self.canvas
        cw, ch = c.winfo_width(), c.winfo_height()
        if cw < 2 or ch < 2:
            return
        iw, ih = self._pil.size
        s  = min(cw / iw, ch / ih)
        nw, nh = max(1, int(iw * s)), max(1, int(ih * s))
        # BILINEAR 比 LANCZOS 快很多，显示差别肉眼难以分辨
        resized = self._pil.resize((nw, nh), Image.BILINEAR)
        self._photo = ImageTk.PhotoImage(resized)
        c.delete('all')
        c.create_image(cw // 2, ch // 2, anchor='center', image=self._photo)

    def _on_resize(self, e):
        # 窗口拖动时防抖：停止拖动 80ms 后才重绘，避免频繁 resize
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._draw)

    def _draw_placeholder(self, msg, color=None):
        c = self.canvas
        cw = c.winfo_width()  or 300
        ch = c.winfo_height() or 200
        c.delete('all')
        c.create_text(cw // 2, ch // 2, text=msg,
                      fill=color or TEXT_MUT, font=F(11))

    def clear(self):
        self._pil = None
        self._cur_path = None
        self.canvas.delete('all')
        self.fname.config(text='—')
        self.lbl_res.config(text='')


# ══════════════════════════════════════════════════════
# 主应用
# ══════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('视觉数据集标注查看器')
        self.configure(bg=BG)
        self.geometry('1700x980')
        self.minsize(1100, 700)

        self.dirs        = {'input': None, 'ref': None, 'result': None}
        self.files       = {'input': {}, 'ref': {}, 'result': {}}
        self.txt_files   = {}
        self.txt_content = {}
        self.file_names  = []
        self.filtered    = []
        self.cur         = -1
        self.filter_mode = 'all'
        self.tag_filter  = None
        self._modified   = False
        self._mode       = tk.StringVar(value='one')

        self._thumb_rows  = 1          # 缩略图行数（随sash变化）
        self._thumb_cache = {}
        self._thumb_items = []
        self._tooltip     = None
        self._panels      = {}
        self._pil_cache   = {}  # path->PIL, LRU cap 80
        self._preload_job = None
        self._panel_sizes  = {}   # key -> (w,h)，用于分辨率比较
        self._res_mismatch = set()  # 分辨率不一致的文件名集合

        # AI 标注服务
        self._cap_proc         = None   # subprocess，常驻后台
        self._cap_queue        = queue.Queue()
        self._cap_pending      = {}     # id -> callback
        self._cap_id           = 0
        self._cap_ready        = False
        self._cap_model_loaded = False  # 模型是否已加载进显存

        self._build()
        self._bind_keys()

    # ══════════════════════════════════════
    # 布局构建
    # ══════════════════════════════════════

    def _build(self):
        self._build_toolbar()
        self._pw = tk.PanedWindow(self, orient='horizontal',
                              bg=BORDER, sashwidth=5, bd=0, sashrelief='flat')
        self._pw.pack(fill='both', expand=True)
        self._build_left(self._pw)
        self._build_center(self._pw)
        self._build_right(self._pw)
        # 延迟设置初始比例：左220 / 中自适应 / 右210
        self.after(100, self._set_default_sash)
        self.after(50, self._update_thumb_height)

    def _set_default_sash(self):
        try:
            total = self.winfo_width()
            self._pw.sash_place(0, 230, 0)
            self._pw.sash_place(1, total - 215, 0)
        except Exception:
            pass

    # ── 工具栏 ──────────────────────────────

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill='x')

        L = tk.Frame(bar, bg=SURFACE)
        L.pack(side='left', padx=8, pady=7)

        tk.Label(L, text='视觉数据集标注查看器', bg=SURFACE, fg=ACCENT,
                 font=F(12, bold=True)).pack(side='left', padx=(4,14))

        # 模式切换
        mf = tk.Frame(L, bg=SURFACE2, highlightthickness=1, highlightbackground=BORDER)
        mf.pack(side='left', padx=(0,12))
        for txt, val in [('单图','one'), ('双图','two'), ('三图','three')]:
            tk.Radiobutton(mf, text=txt, variable=self._mode, value=val,
                           bg=SURFACE2, fg=TEXT_DIM, selectcolor=SURFACE3,
                           activebackground=SURFACE2, font=F(10), cursor='hand2',
                           command=self._on_mode).pack(side='left', padx=10, pady=5)

        self._vsep(L)

        # 文件夹按钮
        self._fbtns = {}
        for key, lbl, color in [('input','📂 输入图',GREEN),
                                  ('ref',  '📂 参考图',YELLOW),
                                  ('result','📂 结果图',ACCENT)]:
            b = self._tbtn(L, lbl, lambda k=key: self._sel(k), fg=color)
            b.pack(side='left', padx=2)
            lb = tk.Label(L, text='未选择', bg=SURFACE, fg=TEXT_MUT, font=F(10))
            lb.pack(side='left', padx=(3,10))
            self._fbtns[key] = (b, lb)

        R = tk.Frame(bar, bg=SURFACE)
        R.pack(side='right', padx=10, pady=7)

        # AI 标注按钮
        self._tbtn(R, '🤖 AI 标注', self._open_caption_panel,
                   fg=ACCENT).pack(side='right', padx=(0,4))
        self._vsep(R)

        # 删除按钮
        self.btn_del = self._tbtn(R, '🗑 删除当前  Del', self._delete_current,
                                   fg=RED, state='disabled')
        self.btn_del.pack(side='right', padx=(0,4))
        self._vsep(R)

        self.lbl_mod = tk.Label(R, text='● 未保存', bg=SURFACE, fg=YELLOW, font=F(10))
        self.btn_save = self._tbtn(R, '💾 保存  Ctrl+S', self._save,
                                    fg=ACCENT, state='disabled')
        self.btn_save.pack(side='right', padx=(6,0))
        self._vsep(R)

        self.btn_next = self._navbtn(R, '▶', lambda: self._nav(1))
        self.btn_next.pack(side='right', padx=2)
        self.lbl_ctr = tk.Label(R, text='0 / 0', bg=SURFACE, fg=TEXT_DIM,
                                  font=F(11, mono=True), width=8, anchor='center')
        self.lbl_ctr.pack(side='right')
        self.btn_prev = self._navbtn(R, '◀', lambda: self._nav(-1))
        self.btn_prev.pack(side='right', padx=2)

        tk.Frame(self, bg=BORDER, height=1).pack(fill='x')
        self._update_ref_vis()

    # ── 左侧：列表 ──────────────────────────

    def _build_left(self, pw):
        F_ = tk.Frame(pw, bg=SURFACE, width=230)
        pw.add(F_, minsize=180)

        # 状态筛选
        fb = tk.Frame(F_, bg=SURFACE, pady=6)
        fb.pack(fill='x', padx=8)
        tk.Label(fb, text='筛选', bg=SURFACE, fg=TEXT_DIM, font=F(10)
                 ).pack(side='left', padx=(2,6))
        self.fbtn = {}
        for lbl,key,c in [('全部','all',TEXT_DIM),('缺输入','no_input',ORANGE),
                           ('缺结果','no_result',ORANGE),('缺TXT','no_txt',YELLOW),
                           ('分辨率异','res_mismatch',YELLOW),
                           ('缺参考图','no_ref',ORANGE)]:
            b = tk.Button(fb, text=lbl, bg=SURFACE2, fg=c, relief='flat', bd=0,
                          font=F(9), padx=5, pady=3, cursor='hand2',
                          command=lambda k=key: self._set_filter(k))
            b.pack(side='left', padx=2)
            self.fbtn[key] = b
        self._hl_filter('all')
        self.fbtn['no_ref'].config(state='disabled', fg=TEXT_MUT)    # 默认禁用
        self.fbtn['no_input'].config(state='disabled', fg=TEXT_MUT)  # 单图默认禁用
        tk.Frame(F_, bg=BORDER, height=1).pack(fill='x')

        # Tag 搜索
        tr = tk.Frame(F_, bg=SURFACE, pady=5)
        tr.pack(fill='x', padx=8)
        tk.Label(tr, text='Tag搜', bg=SURFACE, fg=TEXT_DIM, font=F(10)
                 ).pack(side='left', padx=(2,4))
        self._tv = tk.StringVar()
        te = tk.Entry(tr, textvariable=self._tv, bg=SURFACE2, fg=TEXT,
                       insertbackground=ACCENT, relief='flat', bd=0,
                       font=F(10, mono=True),
                       highlightthickness=1, highlightbackground=BORDER)
        te.pack(side='left', fill='x', expand=True, ipady=3)
        te.bind('<Return>', lambda e: self._tag_filter())
        self._tbtn(tr, '×', self._clear_tag_filter, fg=TEXT_DIM).pack(side='left', padx=(3,0))
        self._tv.trace_add('write', lambda *a: self.after(280, self._tag_filter))
        tk.Frame(F_, bg=BORDER, height=1).pack(fill='x')

        # 统计栏
        self.lbl_stats = tk.Label(F_, text='', bg=SURFACE, fg=TEXT_MUT,
                                   font=F(9), anchor='w', padx=10, pady=4)
        self.lbl_stats.pack(fill='x')
        tk.Frame(F_, bg=BORDER, height=1).pack(fill='x')

        # 文件列表
        lf = tk.Frame(F_, bg=SURFACE)
        lf.pack(fill='both', expand=True)
        sb = tk.Scrollbar(lf, bg=SURFACE2, troughcolor=SURFACE, relief='flat', bd=0, width=5)
        sb.pack(side='right', fill='y')
        self.lb = tk.Listbox(lf, bg=SURFACE, fg=TEXT_DIM,
                              selectbackground=SURFACE3, selectforeground=TEXT,
                              activestyle='none', relief='flat', bd=0,
                              font=F(10), yscrollcommand=sb.set,
                              highlightthickness=0, exportselection=False, cursor='hand2')
        self.lb.pack(side='left', fill='both', expand=True)
        sb.config(command=self.lb.yview)
        self.lb.bind('<<ListboxSelect>>', self._on_sel)
        self.lb.bind('<Motion>', self._on_hover)
        self.lb.bind('<Leave>',  self._hide_tip)

    # ── 中间：缩略图 + 图片 + Tag ───────────

    def _build_center(self, pw):
        self._center = tk.Frame(pw, bg=BG)
        pw.add(self._center, minsize=750)

        # 缩略图
        tw = tk.Frame(self._center, bg=SURFACE)
        tw.pack(fill='x')
        th = tk.Frame(tw, bg=SURFACE, pady=5)
        th.pack(fill='x')
        tk.Label(th, text='缩略图对比', bg=SURFACE, fg=TEXT_DIM,
                 font=F(10), padx=12).pack(side='left')
        tk.Label(th, text='滚轮左右 · 点击跳转', bg=SURFACE, fg=TEXT_MUT,
                 font=F(9), padx=4).pack(side='left')
        tk.Frame(tw, bg=BORDER, height=1).pack(fill='x')
        self._tf = tk.Frame(tw, bg=SURFACE, height=THUMB_H+44)
        self._tf.pack(fill='x'); self._tf.pack_propagate(False)
        hsc = tk.Scrollbar(self._tf, orient='horizontal', bg=SURFACE2,
                            troughcolor=SURFACE, relief='flat', bd=0, width=5)
        hsc.pack(side='bottom', fill='x')
        self.tcv = tk.Canvas(self._tf, bg=SURFACE, highlightthickness=0,
                              xscrollcommand=hsc.set)
        self.tcv.pack(fill='both', expand=True)
        hsc.config(command=self.tcv.xview)
        self.ti = tk.Frame(self.tcv, bg=SURFACE)
        self.tcv.create_window(0, 0, anchor='nw', window=self.ti)
        self.ti.bind('<Configure>', lambda e: self.tcv.config(
            scrollregion=self.tcv.bbox('all')))
        for w in (self.tcv, self.ti, tw):
            w.bind('<MouseWheel>', self._thsc)
            w.bind('<Button-4>',   self._thsc)
            w.bind('<Button-5>',   self._thsc)

        # 拖拽调高
        sash = tk.Frame(self._center, bg=BORDER, height=5, cursor='sb_v_double_arrow')
        sash.pack(fill='x')
        sash.bind('<B1-Motion>', self._on_thumb_sash)
        tk.Frame(self._center, bg=BORDER, height=1).pack(fill='x')

        # 图片区
        self._img_row = tk.Frame(self._center, bg=BG)
        self._img_row.pack(fill='both', expand=True)
        self._mk_panels()

        tk.Frame(self._center, bg=BORDER, height=1).pack(fill='x')

        # 分辨率提示栏
        res_bar = tk.Frame(self._center, bg=SURFACE)
        res_bar.pack(fill='x')
        self.lbl_res_warn = tk.Label(res_bar, text='', bg=SURFACE, fg=SURFACE,
                                      font=F(10), pady=4, padx=12)
        self.lbl_res_warn.pack(side='left')
        tk.Frame(self._center, bg=BORDER, height=1).pack(fill='x')

        # Tag 编辑
        tag_hdr = tk.Frame(self._center, bg=SURFACE, pady=6)
        tag_hdr.pack(fill='x')
        tk.Label(tag_hdr, text='📝 提示词 Tags', bg=SURFACE, fg=TEXT_DIM,
                 font=F(11, bold=True), padx=12).pack(side='left')
        self.lbl_txt = tk.Label(tag_hdr, text='', bg=SURFACE, fg=TEXT_MUT, font=F(10))
        self.lbl_txt.pack(side='left', padx=8)
        tk.Button(tag_hdr, text='🌐 翻译', command=self._translate_tags,
                  bg=SURFACE2, fg=TEXT_DIM, relief='flat', font=F(9),
                  cursor='hand2', activebackground=SURFACE3,
                  bd=0, padx=8, pady=2).pack(side='right', padx=8)
        tk.Frame(self._center, bg=BORDER, height=1).pack(fill='x')
        self.tag_panel = TagPanel(self._center, on_change=self._on_tags)
        self.tag_panel.pack(fill='x', ipady=2)

    # ── 右侧：全局Tag ────────────────────────

    def _build_right(self, pw):
        right_frame = tk.Frame(pw, bg=SURFACE)
        pw.add(right_frame, minsize=160)

        # 全局 Tag 面板（占大部分高度）
        self.gtag = GlobalTagPanel(right_frame, on_add=self._add_tag,
                                    on_filter=self._on_gtag_filter)
        self.gtag.pack(fill='both', expand=True)

        # 批量操作区（固定在底部）
        tk.Frame(right_frame, bg=BORDER, height=1).pack(fill='x')
        batch_hdr = tk.Frame(right_frame, bg=SURFACE, pady=5)
        batch_hdr.pack(fill='x', padx=8)
        tk.Label(batch_hdr, text='批量操作', bg=SURFACE, fg=TEXT_DIM,
                 font=F(10, bold=True)).pack(side='left')
        tk.Label(batch_hdr, text='作用于当前筛选', bg=SURFACE, fg=TEXT_MUT,
                 font=F(9)).pack(side='left', padx=6)

        tk.Frame(right_frame, bg=BORDER, height=1).pack(fill='x')
        batch_row = tk.Frame(right_frame, bg=SURFACE, pady=6)
        batch_row.pack(fill='x', padx=8)
        self._tbtn(batch_row, '＋ 添加 Tag', self._batch_add, fg=GREEN).pack(fill='x', pady=2)
        self._tbtn(batch_row, '－ 删除 Tag', self._batch_del, fg=RED).pack(fill='x', pady=2)
        self._tbtn(batch_row, '⇄  替换 Tag',  self._batch_rep, fg=YELLOW).pack(fill='x', pady=2)
        tk.Frame(right_frame, bg=BORDER, height=1).pack(fill='x')

    def _on_gtag_filter(self, tag):
        """右侧全局Tag单击 → 写入左侧Tag搜索框触发筛选"""
        self._tv.set(tag or '')
        if tag:
            self.tag_filter = tag.lower()
        else:
            self.tag_filter = None
        self._apply()

    # ── 辅助 ────────────────────────────────

    def _tbtn(self, p, t, cmd, fg=TEXT, state='normal'):
        return tk.Button(p, text=t, command=cmd, bg=SURFACE2, fg=fg,
                         relief='flat', bd=0, activebackground=SURFACE3,
                         activeforeground=TEXT, padx=9, pady=5,
                         font=F(10), state=state, cursor='hand2')

    def _navbtn(self, p, t, cmd):
        return tk.Button(p, text=t, command=cmd, bg=SURFACE2, fg=TEXT_DIM,
                         relief='flat', bd=0, activebackground=SURFACE3,
                         activeforeground=TEXT, padx=11, pady=5,
                         font=F(11), state='disabled', cursor='hand2')

    def _vsep(self, p):
        tk.Frame(p, bg=BORDER, width=1, height=20).pack(side='left', padx=10, pady=4)

    def _mk_panels(self):
        for w in self._img_row.winfo_children(): w.destroy()
        self._panels = {}
        self._panel_sizes = {}
        SHOW_RES = {'input': True, 'ref': False, 'result': True}
        m = self._mode.get()
        if m == 'one':
            specs = [('result', '📤 结果图', ACCENT)]
        elif m == 'two':
            specs = [('input','📥 输入图',GREEN),('result','📤 结果图',ACCENT)]
        else:
            specs = [('input','📥 输入图',GREEN),('ref','📋 参考图',YELLOW),
                     ('result','📤 结果图',ACCENT)]
        for i,(key,lbl,color) in enumerate(specs):
            if i: tk.Frame(self._img_row, bg=BORDER, width=1).pack(side='left', fill='y')
            # 参考图不参与分辨率比较
            cb = (lambda k=key: lambda w,h: self._on_panel_size(k, w, h))() if key != 'ref' else None
            p = ImgPanel(self._img_row, lbl, color, self._zoom,
                         show_resolution=SHOW_RES[key],
                         on_size_known=cb)
            p.pack(side='left', fill='both', expand=True)
            self._panels[key] = p

    def _on_panel_size(self, key, w, h):
        """某个面板图片加载完成，记录尺寸并检查是否一致"""
        self._panel_sizes[key] = (w, h)
        self._check_res()

    def _check_res(self):
        """比较 input 和 result 分辨率；更新提示栏 + 左侧列表颜色"""
        si = self._panel_sizes.get('input')
        sr = self._panel_sizes.get('result')
        name = self.filtered[self.cur] if 0 <= self.cur < len(self.filtered) else None

        if si and sr and name:
            mismatch = (si != sr)
            if mismatch:
                self._res_mismatch.add(name)
                self.lbl_res_warn.config(
                    text=f'⚠  分辨率不一致    输入 {si[0]}×{si[1]}  vs  结果 {sr[0]}×{sr[1]}',
                    fg=YELLOW, bg='#252008')
            else:
                self._res_mismatch.discard(name)
                self.lbl_res_warn.config(
                    text=f'✓  分辨率一致  {si[0]} × {si[1]}',
                    fg=GREEN, bg=SURFACE)
            # 刷新该条目颜色
            if self.cur < self.lb.size():
                inp, res = self.files['input'], self.files['result']
                ht = name in self.txt_files
                hi = name in inp; hr = name in res
                if not hi or not hr:   fg = ORANGE
                elif mismatch:         fg = YELLOW
                elif not ht:           fg = '#888840'
                else:                  fg = TEXT_DIM
                self.lb.itemconfig(self.cur, fg=fg)
        elif si or sr:
            self.lbl_res_warn.config(text='', fg=SURFACE, bg=SURFACE)

    # ══════════════════════════════════════
    # 模式切换
    # ══════════════════════════════════════

    def _on_mode(self):
        self._update_ref_vis(); self._mk_panels()
        self._update_thumb_height()
        if self.filtered:
            self._build_thumbs()
            self._render_list()
        if self.cur >= 0 and self.filtered: self._load(self.cur)

    def _update_thumb_height(self):
        m = self._mode.get()
        h = THUMB_H + 44 if m == 'one' else THUMB_H * 2 + 44
        self._tf.config(height=h)
        self.after(10, lambda: self._recalc_thumb_size(h))

    def _on_thumb_sash(self, e):
        new_h = max(60, e.y_root - self._tf.winfo_rooty())
        self._tf.config(height=new_h)
        if hasattr(self, '_th_sash_job'):
            self.after_cancel(self._th_sash_job)
        self._th_sash_job = self.after(180, lambda: self._recalc_thumb_size(new_h))

    def _recalc_thumb_size(self, tf_h=None):
        """根据缩略图区域高度计算能放几行缩略图，行数变化时重建"""
        if tf_h is None:
            tf_h = self._tf.winfo_height()
        # 每行高度 = 缩略图 + 文件名标签 + 上下间距
        slot_h = THUMB_H + 26
        rows = max(1, (tf_h - 8) // slot_h)
        if rows == self._thumb_rows:
            return  # 行数没变，不重建
        self._thumb_rows = rows
        self._thumb_cache.clear()
        if self.filtered:
            self._build_thumbs()

    def _update_ref_vis(self):
        m = self._mode.get()
        # 参考图按钮：仅三图模式显示
        btn, lb = self._fbtns['ref']
        if m == 'three':
            btn.pack(side='left', padx=2)
            lb.pack(side='left', padx=(3,10))
        else:
            btn.pack_forget()
            lb.pack_forget()
        # 输入图按钮：单图模式隐藏
        btn_in, lb_in = self._fbtns['input']
        if m == 'one':
            btn_in.pack_forget()
            lb_in.pack_forget()
        else:
            btn_in.pack(side='left', padx=2)
            lb_in.pack(side='left', padx=(3,10))
        # 筛选按钮：缺输入仅双图/三图有效，缺参考图仅三图有效
        if hasattr(self, 'fbtn'):
            def _fbtn_state(key, enabled):
                b = self.fbtn[key]
                if enabled:
                    b.config(state='normal', fg={'no_input':ORANGE,'no_ref':ORANGE}.get(key, TEXT_DIM))
                else:
                    b.config(state='disabled', fg=TEXT_MUT)
                    if self.filter_mode == key:
                        self._set_filter('all')
            _fbtn_state('no_input', m != 'one')
            _fbtn_state('no_ref',   m == 'three')

    # ══════════════════════════════════════
    # 文件夹选择
    # ══════════════════════════════════════

    def _sel(self, key):
        names = {'input':'输入图','ref':'参考图','result':'结果图'}
        d = filedialog.askdirectory(title=f'选择{names[key]}文件夹')
        if not d: return
        p = Path(d)
        self.dirs[key]  = p
        self.files[key] = {f.stem: f for f in p.iterdir()
                            if f.is_file() and f.suffix.lower() in IMAGE_EXTS}
        btn, lb = self._fbtns[key]
        lb.config(text=f'{p.name}（{len(self.files[key])}张）', fg=GREEN)

        if key == 'result':
            self.txt_files   = {f.stem: f for f in p.iterdir()
                                 if f.is_file() and f.suffix.lower() == '.txt'}
            self.txt_content = {}
            for nm, fp in self.txt_files.items():
                try:    self.txt_content[nm] = fp.read_text(encoding='utf-8')
                except: self.txt_content[nm] = fp.read_text(encoding='gbk', errors='replace')

        self._thumb_cache.clear(); self._rebuild()

    # ══════════════════════════════════════
    # 删除当前
    # ══════════════════════════════════════

    def _delete_current(self):
        if self.cur < 0 or not self.filtered: return
        name = self.filtered[self.cur]

        # 统计将删除的文件
        to_del = []
        for key in ('input','ref','result'):
            p = self.files[key].get(name)
            if p and p.exists(): to_del.append(p)
        if name in self.txt_files:
            tp = self.txt_files[name]
            if tp.exists(): to_del.append(tp)

        if not to_del:
            messagebox.showinfo('提示', '没有找到可删除的文件'); return

        trash_label = '移至回收站' if send2trash else '永久删除'
        detail = '\n'.join(f'  {p.name}' for p in to_del)
        ok = messagebox.askyesno(
            f'确认{trash_label}',
            f'将{trash_label}以下 {len(to_del)} 个文件：\n\n{detail}\n\n确认？',
            icon='warning')
        if not ok: return

        errors = []
        for p in to_del:
            try: _trash(p)
            except Exception as e: errors.append(f'{p.name}: {e}')

        if errors:
            messagebox.showerror('部分删除失败', '\n'.join(errors))

        # 从内存移除
        for key in ('input','ref','result'):
            self.files[key].pop(name, None)
        self.txt_files.pop(name, None)
        self.txt_content.pop(name, None)
        self._thumb_cache.pop(name, None)
        if name in self.file_names: self.file_names.remove(name)
        if name in self.filtered:   self.filtered.remove(name)

        # 跳到下一个（或上一个）
        total = len(self.filtered)
        if total == 0:
            self.cur = -1; self._render_list(); self._update_stats()
            self._update_nav(); self._clear_panels(); return

        self.cur = min(self.cur, total - 1)
        self._render_list()
        self._update_stats()
        self._update_global_tags()
        self._build_thumbs()
        self._load(self.cur)

    # ══════════════════════════════════════
    # 筛选 & 列表
    # ══════════════════════════════════════

    def _nkey(self, s):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]

    def _rebuild(self):
        names = set()
        for k in ('input','ref','result'): names |= set(self.files[k])
        self.file_names = sorted(names, key=self._nkey)
        self._update_global_tags()
        self._tv.set(''); self.tag_filter = None
        self._apply()

    def _set_filter(self, m):
        self.filter_mode = m; self._hl_filter(m); self._apply()

    def _tag_filter(self):
        tv = self._tv.get().strip().lower()
        self.tag_filter = tv if tv else None; self._apply()

    def _clear_tag_filter(self):
        self.tag_filter = None; self._tv.set('')
        if hasattr(self, 'gtag'): self.gtag.sync_filter(None)
        self._apply()

    def _apply(self):
        inp, res, ref = self.files['input'], self.files['result'], self.files['ref']
        m = self.filter_mode
        if   m == 'all':          base = list(self.file_names)
        elif m == 'no_input':     base = [n for n in self.file_names if n not in inp]
        elif m == 'no_result':    base = [n for n in self.file_names if n not in res]
        elif m == 'no_txt':       base = [n for n in self.file_names if n not in self.txt_files]
        elif m == 'res_mismatch': base = [n for n in self.file_names if n in self._res_mismatch]
        elif m == 'no_ref':       base = [n for n in self.file_names if n not in ref]
        else:                     base = list(self.file_names)

        if self.tag_filter:
            tf = self.tag_filter
            base = [n for n in base
                    if any(tf in t.lower() for t in self.txt_content.get(n,'').split(','))]

        self.filtered = base
        self._render_list(); self._update_stats(); self._update_nav(); self._build_thumbs()
        if self.filtered: self._load(0)
        else: self.cur = -1; self._clear_panels()

    def _hl_filter(self, m):
        c = {'all':TEXT_DIM,'no_input':ORANGE,'no_result':ORANGE,
             'no_txt':YELLOW,'res_mismatch':YELLOW,'no_ref':ORANGE}
        for k, b in self.fbtn.items():
            a = k==m
            b.config(bg=ACCENT if a else SURFACE2, fg='white' if a else c[k],
                     font=F(9,bold=True) if a else F(9))

    def _update_stats(self):
        inp, res, ref = self.files['input'], self.files['result'], self.files['ref']
        t  = len(self.file_names)
        ni = sum(1 for n in self.file_names if n not in inp)
        nr = sum(1 for n in self.file_names if n not in res)
        nt = sum(1 for n in self.file_names if n not in self.txt_files)
        nm = len(self._res_mismatch)
        nref = sum(1 for n in self.file_names if n not in ref)
        s  = len(self.filtered)
        parts = [f'共 {t} 个']
        if ni: parts.append(f'缺输入 {ni}')
        if nr: parts.append(f'缺结果 {nr}')
        if nt: parts.append(f'缺TXT {nt}')
        if nref and self._mode.get() == 'three': parts.append(f'缺参考图 {nref}')
        if nm: parts.append(f'分辨率异 {nm}')
        if s != t: parts.append(f'显示 {s}')
        self.lbl_stats.config(text='  ·  '.join(parts))

    def _update_global_tags(self):
        c = Counter()
        for content in self.txt_content.values():
            for t in content.split(','):
                t = t.strip()
                if t: c[t] += 1
        self.gtag.update_tags(c)

    def _render_list(self):
        inp, res, ref = self.files['input'], self.files['result'], self.files['ref']
        m = self._mode.get()
        self.lb.delete(0, 'end')
        for name in self.filtered:
            hi = (name in inp) or (m == 'one')
            hr = name in res
            hf = (name in ref) or (m != 'three')
            ht = name in self.txt_files
            icon = '⚠ ' if not hi or not hr or not hf else ('○ ' if not ht else '● ')
            self.lb.insert('end', icon + name)
        self._recolor_list()

    def _recolor_list(self):
        """根据状态 + 分辨率不一致重新着色列表"""
        inp, res, ref = self.files['input'], self.files['result'], self.files['ref']
        m = self._mode.get()
        for i, name in enumerate(self.filtered):
            hi = (name in inp) or (m == 'one')
            hr = name in res
            hf = (name in ref) or (m != 'three')
            ht = name in self.txt_files
            if not hi or not hr or not hf:
                fg = ORANGE
            elif name in self._res_mismatch:
                fg = YELLOW
            elif not ht:
                fg = '#888840'   # 暗黄，缺TXT
            else:
                fg = TEXT_DIM
            self.lb.itemconfig(i, fg=fg)

    def _refresh_item(self, i):
        if i >= len(self.filtered): return
        name = self.filtered[i]
        inp, res, ref = self.files['input'], self.files['result'], self.files['ref']
        m = self._mode.get()
        hi = (name in inp) or (m == 'one')
        hr = name in res
        hf = (name in ref) or (m != 'three')
        ht = name in self.txt_files
        icon = '⚠ ' if not hi or not hr or not hf else ('○ ' if not ht else '● ')
        self.lb.delete(i); self.lb.insert(i, icon + name)
        if not hi or not hr or not hf:
            fg = ORANGE
        elif name in self._res_mismatch:
            fg = YELLOW
        elif not ht:
            fg = '#888840'
        else:
            fg = TEXT_DIM
        self.lb.itemconfig(i, fg=fg)
        if i == self.cur: self.lb.selection_set(i)

    # ── Tooltip ──────────────────────────────

    def _on_hover(self, e):
        idx = self.lb.nearest(e.y)
        if idx < 0 or idx >= len(self.filtered): return
        content = self.txt_content.get(self.filtered[idx],'')
        if not content: self._hide_tip(); return
        self._show_tip(e, content)

    def _show_tip(self, e, text):
        self._hide_tip()
        tags = [t.strip() for t in text.split(',') if t.strip()]
        lines = []; line = []
        for t in tags:
            line.append(t)
            if sum(len(x)+2 for x in line) > 58:
                lines.append(', '.join(line[:-1])); line = [t]
        if line: lines.append(', '.join(line))
        tip = tk.Toplevel(self); tip.wm_overrideredirect(True)
        tip.wm_geometry(f'+{e.x_root+14}+{e.y_root+6}'); tip.configure(bg=BORDER)
        tk.Label(tip, text='\n'.join(lines), bg='#1a1a2c', fg=TAG_FG,
                 font=F(10, mono=True), justify='left', padx=10, pady=6).pack()
        self._tooltip = tip

    def _hide_tip(self, e=None):
        if self._tooltip:
            try: self._tooltip.destroy()
            except: pass
            self._tooltip = None

    # ══════════════════════════════════════
    # 批量操作
    # ══════════════════════════════════════

    def _batch_add(self):
        if not self.dirs['result']:
            messagebox.showwarning('提示','请先选择结果图文件夹'); return
        tag = simpledialog.askstring('批量添加 Tag',
            f'对当前筛选的 {len(self.filtered)} 个文件操作\n\n输入 Tag（逗号分隔多个）：', parent=self)
        if not tag: return
        new_tags = [t.strip() for t in tag.split(',') if t.strip()]
        count = 0
        for name in self.filtered:
            tags = [t.strip() for t in self.txt_content.get(name,'').split(',') if t.strip()]
            ch = any(nt not in tags and (tags.append(nt) or True) for nt in new_tags)
            if ch: self._write(name, ', '.join(tags)); count += 1
        self._post_batch(count, f'已添加：{", ".join(new_tags)}')

    def _batch_del(self):
        save_dir = self.dirs['result'] or self.dirs['input']
        if not save_dir:
            messagebox.showwarning('提示','请先选择输入图或结果图文件夹'); return
        # 有筛选 Tag 时直接删除，无需弹框
        active = getattr(self.gtag, '_filter_tag', None)
        if active:
            tag = active
        else:
            tag = simpledialog.askstring('批量删除 Tag',
                f'对当前筛选的 {len(self.filtered)} 个文件操作\n\n输入要删除的 Tag（模糊匹配，逗号分隔）：', parent=self)
            if not tag: return
        del_tags = [t.strip().lower() for t in tag.split(',') if t.strip()]
        count = 0
        for name in self.filtered:
            tags = [t.strip() for t in self.txt_content.get(name,'').split(',') if t.strip()]
            new  = [t for t in tags if not any(d in t.lower() for d in del_tags)]
            if len(new) != len(tags): self._write(name, ', '.join(new)); count += 1
        self._post_batch(count, f'已删除含 "{tag}" 的 Tag')

    def _batch_rep(self):
        if not self.dirs['result']:
            messagebox.showwarning('提示','请先选择结果图文件夹'); return
        old = simpledialog.askstring('批量替换（1/2）','输入要替换的旧 Tag：', parent=self)
        if not old: return
        new = simpledialog.askstring('批量替换（2/2）',
            f'旧 Tag：{old}\n输入新 Tag（留空则删除）：', parent=self)
        if new is None: return
        old, new = old.strip(), new.strip()
        count = 0
        for name in self.filtered:
            tags = [t.strip() for t in self.txt_content.get(name,'').split(',') if t.strip()]
            nt = [new if t==old else t for t in tags]
            if not new: nt = [t for t in nt if t]
            if nt != tags: self._write(name, ', '.join(nt)); count += 1
        self._post_batch(count, f'"{old}" → "{new or "（删除）"}"')

    def _post_batch(self, count, msg):
        self._update_global_tags(); self._render_list(); self._update_stats()
        if 0 <= self.cur < len(self.filtered):
            self._load_tags(self.filtered[self.cur])
        messagebox.showinfo('批量完成', f'{msg}\n\n影响 {count} 个文件')

    # ══════════════════════════════════════
    # 缩略图
    # ══════════════════════════════════════

    def _build_thumbs(self):
        for w in self.ti.winfo_children(): w.destroy()
        self._thumb_items = []
        inp, res = self.files['input'], self.files['result']
        single = self._mode.get() == 'one'
        rows = self._thumb_rows
        for idx, name in enumerate(self.filtered):
            grid_row = idx % rows
            grid_col = idx // rows
            col = tk.Frame(self.ti, bg=SURFACE2, cursor='hand2',
                           highlightthickness=2, highlightbackground=SURFACE2)
            col.grid(row=grid_row, column=grid_col, padx=4, pady=4, sticky='n')
            if not single:
                il = tk.Label(col, bg='#0c0c14', width=THUMB_W, height=THUMB_H, relief='flat')
                il.pack()
                tk.Frame(col, bg=BORDER, height=1).pack(fill='x')
            else:
                il = None
            rl = tk.Label(col, bg='#0c0c14', width=THUMB_W, height=THUMB_H, relief='flat')
            rl.pack()
            short = name[:15]+'…' if len(name)>16 else name
            fg = ORANGE if (not single and name not in inp) or name not in res else TEXT_MUT
            nl = tk.Label(col, text=short, bg=SURFACE2, fg=fg, font=F(8), pady=2)
            nl.pack()
            bind_targets = [w for w in (col, il, rl, nl) if w is not None]
            for w in bind_targets:
                w.bind('<Button-1>',   lambda e,i=idx: self._load(i))
                w.bind('<MouseWheel>', self._thsc)
                w.bind('<Button-4>',   self._thsc)
                w.bind('<Button-5>',   self._thsc)
            self._thumb_items.append((name, il, rl, col))
        self.ti.update_idletasks()
        self.tcv.config(scrollregion=self.tcv.bbox('all'))
        threading.Thread(target=self._load_thumbs_bg, daemon=True).start()

    def _load_thumbs_bg(self):
        inp, res = self.files['input'], self.files['result']
        for idx, (name, il, rl, col) in enumerate(self._thumb_items):
            if name not in self._thumb_cache:
                ip = self._mk_th(inp.get(name))
                rp = self._mk_th(res.get(name))
                self._thumb_cache[name] = (ip, rp)
            self.after(0, lambda i=idx, n=name: self._apply_th(i, n))

    def _mk_th(self, path):
        if not path or not path.exists(): return None
        try:
            img = Image.open(path); img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except: return None

    def _apply_th(self, idx, name):
        if idx >= len(self._thumb_items): return
        n, il, rl, col = self._thumb_items[idx]
        if n != name: return
        ip, rp = self._thumb_cache.get(name,(None,None))
        if il is not None:
            if ip: il.config(image=ip, width=THUMB_W, height=THUMB_H); il.image=ip
            else:  il.config(text='—', fg=TEXT_MUT, font=F(9), image='')
        if rp: rl.config(image=rp, width=THUMB_W, height=THUMB_H); rl.image=rp
        else:  rl.config(text='—', fg=TEXT_MUT, font=F(9), image='')
        self._hl_th(self.cur)

    def _hl_th(self, idx):
        for i,(_,il,rl,col) in enumerate(self._thumb_items):
            col.config(highlightbackground=ACCENT if i==idx else SURFACE2)

    def _scroll_th(self, idx):
        total = len(self._thumb_items)
        if total < 2: return
        rows = self._thumb_rows
        # 多行时 idx 对应的网格列 = idx // rows
        grid_col = idx // rows
        total_cols = (total - 1) // rows + 1
        self.tcv.xview_moveto(max(0, min(1, (grid_col - 2) / max(total_cols - 1, 1))))

    def _thsc(self, e):
        d = e.delta if hasattr(e,'delta') and e.delta else (-120 if e.num==5 else 120)
        self.tcv.xview_scroll(-1 if d>0 else 1, 'units')

    # ══════════════════════════════════════
    # 导航
    # ══════════════════════════════════════

    def _bind_keys(self):
        self.bind('<Left>',      lambda e: self._nav(-1))
        self.bind('<Right>',     lambda e: self._nav(1))
        self.bind('<Up>',        lambda e: self._nav(-1))
        self.bind('<Down>',      lambda e: self._nav(1))
        self.bind('<Control-s>', lambda e: self._save())
        self.bind('<Delete>',    lambda e: self._delete_current())

    def _nav(self, d):
        if not self.filtered: return
        n = self.cur + d
        if 0 <= n < len(self.filtered): self._load(n)

    def _on_sel(self, e):
        sel = self.lb.curselection()
        if sel and sel[0] != self.cur: self._load(sel[0])

    def _update_nav(self):
        total = len(self.filtered)
        cur = self.cur+1 if self.cur >= 0 else 0
        self.lbl_ctr.config(text=f'{cur} / {total}')
        self.btn_prev.config(state='normal' if self.cur>0 else 'disabled')
        self.btn_next.config(state='normal' if self.cur<total-1 else 'disabled')
        has = self.cur >= 0 and bool(self.filtered)
        self.btn_del.config(state='normal' if has else 'disabled')

    # ══════════════════════════════════════
    # 加载条目
    # ══════════════════════════════════════

    def _load(self, idx):
        self.cur = idx
        name = self.filtered[idx]
        self.lb.selection_clear(0, 'end')
        self.lb.selection_set(idx)
        self.lb.see(idx)

        # 清理过大的缓存（保留最近 80 张）
        if len(self._pil_cache) > 80:
            old_keys = list(self._pil_cache.keys())[:-40]
            for k in old_keys:
                del self._pil_cache[k]

        # 重置分辨率状态
        self._panel_sizes = {}
        self.lbl_res_warn.config(text='', fg=SURFACE, bg=SURFACE)

        for key, panel in self._panels.items():
            panel.show(self.files[key].get(name), self._pil_cache)

        self._load_tags(name)
        self._update_nav()
        self._hl_th(idx)
        self._scroll_th(idx)

        # 预加载相邻 2 张
        self._schedule_preload(idx)

    def _schedule_preload(self, idx):
        if self._preload_job:
            self.after_cancel(self._preload_job)
        self._preload_job = self.after(200, lambda: self._preload_neighbors(idx))

    def _preload_neighbors(self, idx):
        neighbors = [idx - 1, idx + 1, idx - 2, idx + 2]
        paths_to_load = []
        for ni in neighbors:
            if 0 <= ni < len(self.filtered):
                name = self.filtered[ni]
                for key in self._panels:
                    p = self.files[key].get(name)
                    if p and p.exists() and p not in self._pil_cache:
                        paths_to_load.append(p)

        def _bg():
            for p in paths_to_load:
                if p not in self._pil_cache:
                    try:
                        img = Image.open(p); img.load()
                        self._pil_cache[p] = img
                    except Exception as ex:
                        self._pil_cache[p] = ex

        if paths_to_load:
            threading.Thread(target=_bg, daemon=True).start()

    def _clear_panels(self):
        for p in self._panels.values(): p.clear()
        self.tag_panel.set_tags([])
        self.lbl_txt.config(text='')
        self.lbl_ctr.config(text='0 / 0')
        self.btn_del.config(state='disabled')

    def _zoom(self, panel):
        if not panel._pil: return
        win = tk.Toplevel(self); win.configure(bg='#000'); win.title('预览')
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        iw, ih = panel._pil.size
        s = min(sw * .9 / iw, sh * .9 / ih, 1.0)
        nw, nh = max(1, int(iw*s)), max(1, int(ih*s))
        win.geometry(f'{nw}x{nh}+{(sw-nw)//2}+{(sh-nh)//2}')
        win.resizable(True, True)
        c = tk.Canvas(win, bg='#000', highlightthickness=0)
        c.pack(fill='both', expand=True)
        win._pil = panel._pil; win._photo = None; win._rjob = None

        def rz(e=None):
            if win._rjob: win.after_cancel(win._rjob)
            win._rjob = win.after(60, _do_rz)

        def _do_rz():
            cw, ch = c.winfo_width(), c.winfo_height()
            if cw < 2 or ch < 2: return
            iw2, ih2 = win._pil.size
            s2 = min(cw/iw2, ch/ih2)
            win._photo = ImageTk.PhotoImage(
                win._pil.resize((max(1,int(iw2*s2)), max(1,int(ih2*s2))), Image.LANCZOS))
            c.delete('all')
            c.create_image(cw//2, ch//2, anchor='center', image=win._photo)

        c.bind('<Configure>', rz)
        win.bind('<Escape>', lambda e: win.destroy())
        win.bind('<space>',  lambda e: win.destroy())
        tk.Label(win, text=f'{iw}×{ih}    Esc 关闭', bg='#000', fg='#333344',
                 font=F(9)).place(relx=1, rely=1, anchor='se', x=-8, y=-6)

    # ══════════════════════════════════════
    # Tag 编辑
    # ══════════════════════════════════════

    def _load_tags(self, name):
        path = self.txt_files.get(name)
        content = self.txt_content.get(name,'')
        if path and path.exists():
            self.lbl_txt.config(text=path.name, fg=GREEN)
        else:
            self.lbl_txt.config(text=f'{name}.txt（保存时自动创建）', fg=TEXT_MUT)
        tags = [t.strip() for t in content.split(',') if t.strip()]
        self.tag_panel.set_tags(tags)
        self._modified = False; self._set_mod(False)
        self.btn_save.config(state='normal' if self.dirs['result'] else 'disabled')
        self.gtag.highlight_current(set(tags))

    def _on_tags(self, tags):
        self._modified = True; self._set_mod(True)
        self.gtag.highlight_current(set(tags))

    def _add_tag(self, tag):
        if self.cur < 0: return
        self.tag_panel.add_tag(tag); self.tag_panel.focus_input()

    def _set_mod(self, v):
        if v: self.lbl_mod.pack(side='right', padx=(0,8))
        else: self.lbl_mod.pack_forget()

    def _translate_tags(self):
        import urllib.request, urllib.parse, json, threading
        tags = self.tag_panel.get_tags()
        if not tags:
            return
        text = ', '.join(tags)

        win = tk.Toplevel(self)
        win.title('翻译')
        win.configure(bg=SURFACE)
        win.geometry('480x220')
        win.resizable(True, True)

        lbl = tk.Label(win, text='正在翻译...', bg=SURFACE, fg=TEXT_DIM,
                       font=F(10), wraplength=456, justify='left', anchor='nw')
        lbl.pack(padx=12, pady=12, fill='both', expand=True)
        tk.Button(win, text='关闭', command=win.destroy,
                  bg=SURFACE2, fg=TEXT, relief='flat', padx=16, pady=4,
                  cursor='hand2').pack(pady=(0, 10))

        def do_translate():
            url = ('https://translate.googleapis.com/translate_a/single'
                   '?client=gtx&sl=auto&tl=zh-CN&dt=t&q=' + urllib.parse.quote(text))
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                result = ''.join(item[0] for item in data[0] if item[0])
                if win.winfo_exists():
                    win.after(0, lambda: lbl.config(text=result, fg=TEXT))
            except Exception as e:
                if win.winfo_exists():
                    win.after(0, lambda: lbl.config(text=f'翻译失败: {e}', fg='#e06c75'))

        threading.Thread(target=do_translate, daemon=True).start()

    def _save(self):
        if not self.dirs['result'] or self.cur < 0: return
        name = self.filtered[self.cur]
        content = ', '.join(self.tag_panel.get_tags())
        self._write(name, content)
        self._modified = False; self._set_mod(False)
        self.lbl_txt.config(text=f'{name}.txt', fg=GREEN)
        self._refresh_item(self.cur)
        self._update_stats(); self._update_global_tags()
        orig = self.btn_save.cget('text')
        self.btn_save.config(text='✓ 已保存', fg=GREEN)
        self.after(900, lambda: self.btn_save.config(text=orig, fg=ACCENT))

    def _write(self, name, content):
        save_dir = self.dirs['result'] or self.dirs['input']
        if not save_dir: return
        path = save_dir / (name + '.txt')
        try:
            path.write_text(content, encoding='utf-8')
            self.txt_files[name] = path; self.txt_content[name] = content
        except Exception as e:
            messagebox.showerror('保存失败', str(e))



    # ══════════════════════════════════════
    # AI 标注功能
    # ══════════════════════════════════════

    def _open_caption_panel(self):
        """打开 AI 标注控制面板"""
        if hasattr(self, '_cap_win') and self._cap_win and self._cap_win.winfo_exists():
            self._cap_win.lift(); return

        win = tk.Toplevel(self)
        win.title('🤖 AI 图生提示词')
        win.configure(bg=SURFACE)
        win.geometry('540x620')
        win.resizable(True, True)
        self._cap_win = win

        # ── 模型选择 ──────────────────────────────────
        sec = tk.Frame(win, bg=SURFACE, pady=10)
        sec.pack(fill='x', padx=16)
        tk.Label(sec, text='打标模型', bg=SURFACE, fg=TEXT_DIM,
                 font=F(10, bold=True)).grid(row=0, column=0, sticky='w', pady=4)

        self._cap_model = tk.StringVar(value='wd14')
        model_info = [
            ('wd14',  'WD14 v3',     '快速 · Tag格式 · 400MB · 推荐先用',                GREEN),
            ('qwen',  'Qwen3.5-4B',  '原生多模态 · 支持自定义Prompt · 约8GB · 最新模型', '#c678dd'),
        ]
        for i, (val, name, desc, color) in enumerate(model_info):
            rb = tk.Radiobutton(sec, text=name, variable=self._cap_model, value=val,
                                bg=SURFACE, fg=color, selectcolor=SURFACE3,
                                activebackground=SURFACE, font=F(10, bold=True),
                                cursor='hand2', command=self._on_cap_model_change)
            rb.grid(row=i+1, column=0, sticky='w', padx=(16,0), pady=1)
            tk.Label(sec, text=desc, bg=SURFACE, fg=TEXT_MUT,
                     font=F(9)).grid(row=i+1, column=1, sticky='w', padx=8)

        tk.Frame(win, bg=BORDER, height=1).pack(fill='x')

        # ── 模型参数容器（固定位置，内部切换）────────
        self._cap_opt_container = tk.Frame(win, bg=SURFACE)
        self._cap_opt_container.pack(fill='x', padx=16, pady=0)

        # 描述风格（JoyCaption用）
        self._joy_sec = tk.Frame(self._cap_opt_container, bg=SURFACE, pady=8)
        tk.Label(self._joy_sec, text='描述风格', bg=SURFACE, fg=TEXT_DIM,
                 font=F(10, bold=True)).pack(side='left', padx=(0,12))
        self._cap_mode = tk.StringVar(value='natural')
        for txt, val in [('自然语言','natural'),('详细描述','detail'),
                          ('Tag格式','tag'),('简短','short')]:
            tk.Radiobutton(self._joy_sec, text=txt, variable=self._cap_mode, value=val,
                           bg=SURFACE, fg=TEXT_DIM, selectcolor=SURFACE3,
                           activebackground=SURFACE, font=F(10), cursor='hand2',
                           ).pack(side='left', padx=6)
        self._joy_sec.pack(fill='x')  # 默认显示

        # 自定义 Prompt（Qwen用）
        self._qwen_sec = tk.Frame(self._cap_opt_container, bg=SURFACE, pady=8)
        tk.Label(self._qwen_sec, text='自定义 Prompt', bg=SURFACE, fg='#c678dd',
                 font=F(10, bold=True)).pack(anchor='w', pady=(0,4))
        self._cap_prompt = tk.Text(self._qwen_sec, bg=SURFACE2, fg=TEXT,
                                    insertbackground=ACCENT, relief='flat', bd=0,
                                    font=F(9, mono=True), height=3,
                                    highlightthickness=1, highlightbackground=BORDER,
                                    wrap='word')
        self._cap_prompt.pack(fill='x', ipady=4)
        self._cap_prompt.insert('1.0',
            'Write a short caption for this image suitable for vision model training. '
            'Describe the texture, material, lighting, and color in plain English. '
            'One paragraph, under 60 words.')
        prompt_row = tk.Frame(self._qwen_sec, bg=SURFACE, pady=3)
        prompt_row.pack(fill='x')
        tk.Label(prompt_row, text='最大 Token 数：', bg=SURFACE, fg=TEXT_DIM,
                 font=F(9)).pack(side='left')
        self._cap_max_tokens = tk.StringVar(value='512')
        tk.Spinbox(prompt_row, textvariable=self._cap_max_tokens,
                   from_=64, to=2048, increment=64, width=6,
                   bg=SURFACE2, fg=TEXT, relief='flat', font=F(9),
                   buttonbackground=SURFACE3).pack(side='left', padx=4)
        tk.Label(prompt_row, text='（控制输出长度）', bg=SURFACE, fg=TEXT_MUT,
                 font=F(9)).pack(side='left')

        # 默认隐藏，选 Qwen 时显示

        tk.Frame(win, bg=BORDER, height=1).pack(fill='x')

        # ── 已有TXT处理 ──────────────────────────────
        sec3 = tk.Frame(win, bg=SURFACE, pady=7)
        sec3.pack(fill='x', padx=16)
        tk.Label(sec3, text='已有TXT', bg=SURFACE, fg=TEXT_DIM,
                 font=F(10, bold=True)).pack(side='left', padx=(0,12))
        self._cap_overwrite = tk.StringVar(value='skip')
        for txt, val in [('跳过','skip'),('追加','append'),('覆盖','overwrite')]:
            tk.Radiobutton(sec3, text=txt, variable=self._cap_overwrite, value=val,
                           bg=SURFACE, fg=TEXT_DIM, selectcolor=SURFACE3,
                           activebackground=SURFACE, font=F(10), cursor='hand2',
                           ).pack(side='left', padx=8)

        tk.Frame(win, bg=BORDER, height=1).pack(fill='x')

        # ── 操作按钮 ──────────────────────────────────
        btn_row = tk.Frame(win, bg=SURFACE, pady=10)
        btn_row.pack(fill='x', padx=16)
        self._tbtn(btn_row, '▶  标注当前图', self._caption_current,
                   fg=GREEN).pack(side='left', padx=(0,8))
        self._tbtn(btn_row, '⚡  批量标注全部筛选图', self._caption_batch,
                   fg=ACCENT).pack(side='left')
        self._tbtn(btn_row, '■ 停止', self._caption_stop,
                   fg=RED).pack(side='right')

        tk.Frame(win, bg=BORDER, height=1).pack(fill='x')

        # ── 一键安装依赖 ──────────────────────────────
        dep_row = tk.Frame(win, bg=SURFACE, pady=6)
        dep_row.pack(fill='x', padx=16)
        tk.Label(dep_row, text='首次使用 / 遇到依赖报错时点击：',
                 bg=SURFACE, fg=TEXT_MUT, font=F(9)).pack(side='left', padx=(0,8))
        self._tbtn(dep_row, '🔧 一键安装全部依赖', self._install_deps,
                   fg=YELLOW).pack(side='left')

        tk.Frame(win, bg=BORDER, height=1).pack(fill='x')

        # ── 状态 + 进度条 ─────────────────────────────
        sf = tk.Frame(win, bg=SURFACE, pady=5)
        sf.pack(fill='x', padx=16)
        self._cap_status_lbl = tk.Label(sf, text='● 正在启动服务...', bg=SURFACE,
                                         fg=YELLOW, font=F(10))
        self._cap_status_lbl.pack(side='left')
        self._cap_pct_lbl = tk.Label(sf, text='', bg=SURFACE, fg=TEXT_MUT, font=F(9, mono=True))
        self._cap_pct_lbl.pack(side='right')

        self._cap_progress = tk.Canvas(win, bg=SURFACE2, height=5, highlightthickness=0)
        self._cap_progress.pack(fill='x', padx=0, pady=0)
        self._cap_progress_bar = self._cap_progress.create_rectangle(0, 0, 0, 5,
                                                                       fill=ACCENT, width=0)

        tk.Frame(win, bg=BORDER, height=1).pack(fill='x')

        # ── 日志 ─────────────────────────────────────
        log_frame = tk.Frame(win, bg='#0a0a0d')
        log_frame.pack(fill='both', expand=True)
        lsb = tk.Scrollbar(log_frame, bg=SURFACE2, troughcolor='#0a0a0d',
                            relief='flat', bd=0, width=5)
        lsb.pack(side='right', fill='y')
        self._cap_log = tk.Text(log_frame, bg='#0a0a0d', fg=TEXT_DIM,
                                 font=F(9, mono=True), relief='flat', bd=0,
                                 wrap='word', padx=10, pady=8,
                                 highlightthickness=0, state='disabled',
                                 yscrollcommand=lsb.set)
        self._cap_log.pack(fill='both', expand=True)
        lsb.config(command=self._cap_log.yview)
        # 颜色 tag
        self._cap_log.tag_config('ok',   foreground=GREEN)
        self._cap_log.tag_config('warn', foreground=YELLOW)
        self._cap_log.tag_config('err',  foreground=RED)
        self._cap_log.tag_config('dim',  foreground=TEXT_MUT)

        win.protocol('WM_DELETE_WINDOW', lambda: win.destroy())  # 关窗口不停服务，模型保持在显存
        self._cap_start_service()

    # ── 服务管理 ─────────────────────────────

    def _cap_log_write(self, msg, color=None):
        """向日志区写入一行"""
        if not (hasattr(self, '_cap_log') and self._cap_log.winfo_exists()):
            return
        self._cap_log.config(state='normal')
        if color == GREEN:   ctag = 'ok'
        elif color == YELLOW: ctag = 'warn'
        elif color == RED:    ctag = 'err'
        else:                 ctag = 'dim'
        self._cap_log.insert('end', msg + '\n', ctag)
        self._cap_log.see('end')
        self._cap_log.config(state='disabled')

    def _cap_set_status(self, msg, color=None):
        if hasattr(self, '_cap_status_lbl') and self._cap_status_lbl.winfo_exists():
            self._cap_status_lbl.config(text=msg, fg=color or TEXT_DIM)
        # 同步更新工具栏 AI 按钮颜色提示（可选）

    def _cap_set_progress(self, frac):
        if not (hasattr(self, '_cap_progress') and self._cap_progress.winfo_exists()):
            return
        w = self._cap_progress.winfo_width() or 540
        self._cap_progress.coords(self._cap_progress_bar, 0, 0, int(w * frac), 5)

    def _find_python(self):
        """找到系统中可用的 Python 解释器（打包后 sys.executable 是 exe，不能用）"""
        import sys, shutil
        # 1. 直接运行（非打包）时，sys.executable 就是 python
        if not getattr(sys, 'frozen', False):
            return sys.executable
        # 2. 打包后：依次尝试 python / python3 命令
        for candidate in ('python', 'python3', 'python.exe', 'python3.exe'):
            found = shutil.which(candidate)
            if found:
                return found
        # 3. 常见 Windows 安装路径
        import os
        local = os.environ.get('LOCALAPPDATA', '')
        for ver in ('313','312','311','310','39','38'):
            p = os.path.join(local, 'Programs', 'Python', f'Python{ver}', 'python.exe')
            if os.path.exists(p):
                return p
        return None

    def _cap_start_service(self):
        """启动 caption_service.py 子进程（只启动一次，常驻后台）"""
        if self._cap_proc and self._cap_proc.poll() is None:
            # 服务还在跑，直接标记就绪，不重启
            self._cap_ready = True
            self._cap_set_status('● 服务运行中', GREEN)
            self._cap_log_write('服务已在后台运行 ✓', GREEN)
            if self._cap_model_loaded:
                self._cap_log_write(f'模型已在显存中，可直接标注 ✓', GREEN)
            # 继续轮询队列
            self.after(200, self._cap_poll_queue)
            return
        import sys

        # 定位 caption_service.py（在 exe / py 同目录）
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent
        service_path = (base_dir / 'caption_service.py').resolve()

        if not service_path.exists():
            self._cap_log_write('找不到 caption_service.py，请将其放到程序同目录：', RED)
            self._cap_log_write(f'  {base_dir}', RED)
            self._cap_set_status('● 找不到服务脚本', RED)
            return

        # 找 Python 解释器
        python_exe = self._find_python()
        if not python_exe:
            self._cap_log_write('找不到 Python 解释器！请先安装 Python 3.8+', RED)
            self._cap_log_write('下载：https://www.python.org/downloads/', RED)
            self._cap_set_status('● 找不到 Python', RED)
            return

        self._cap_log_write(f'使用 Python：{python_exe}')
        self._cap_log_write(f'服务脚本：{service_path}')

        try:
            self._cap_proc = subprocess.Popen(
                [python_exe, str(service_path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            self._cap_ready = False
            self._cap_set_status('● 正在启动服务...', YELLOW)
            self._cap_log_write('正在启动 AI 标注服务...')
            t = threading.Thread(target=self._cap_reader_thread, daemon=True)
            t.start()
            self.after(200, self._cap_poll_queue)
        except Exception as e:
            self._cap_log_write(f'启动失败: {e}', RED)
            self._cap_set_status('● 启动失败', RED)

    def _cap_reader_thread(self):
        """后台线程读取子进程 stdout，过滤无关警告"""
        import json as _json
        # 这些关键词出现在行里就跳过（第三方库的警告/提示）
        SKIP_PATTERNS = (
            'warnings.warn', 'UserWarning', 'FutureWarning',
            'DeprecationWarning', 'use_fast', 'torch_dtype',
            'is deprecated', 'will be the default',
            'minor differences', "You'll still be able",
            'Loading checkpoint', 'Some weights',
            'was not initialized', 'This IS expected',
        )
        proc = self._cap_proc
        for line in proc.stdout:
            line = line.strip()
            if not line: continue
            # 跳过警告行
            if any(p in line for p in SKIP_PATTERNS):
                continue
            try:
                obj = _json.loads(line)
                self._cap_queue.put(obj)
            except Exception:
                # 非 JSON 的普通输出也过滤警告
                if not any(p in line for p in SKIP_PATTERNS):
                    self._cap_queue.put({'type': 'log', 'msg': line})
        self._cap_queue.put({'type': 'proc_exit'})

    def _cap_poll_queue(self):
        """主线程轮询队列，处理子进程消息"""
        try:
            while True:
                obj = self._cap_queue.get_nowait()
                self._cap_handle_msg(obj)
        except queue.Empty:
            pass
        # 继续轮询（只要窗口存在）
        if hasattr(self, '_cap_win') and self._cap_win and self._cap_win.winfo_exists():
            self.after(100, self._cap_poll_queue)

    def _cap_handle_msg(self, obj):
        t = obj.get('type')
        if t == 'ready':
            self._cap_ready = True
            self._cap_set_status('● 服务就绪，点击开始标注', GREEN)
            self._cap_log_write('服务就绪 ✓', GREEN)
        elif t == 'log':
            lvl = obj.get('level', 'info')
            msg = obj.get('msg', '')
            color = GREEN if '✓' in msg else YELLOW if '下载' in msg or '安装' in msg else None
            self._cap_log_write(msg, color)
        elif t == 'error':
            self._cap_log_write('⚠ ' + obj.get('msg',''), RED)
            self._cap_set_status('● 出错', RED)
        elif t == 'progress':
            pct = obj.get('pct', 0)
            msg = obj.get('msg', '')
            self._cap_set_progress(pct / 100.0)
            if msg:
                self._cap_set_status(f'● {msg}', YELLOW)
                if hasattr(self, '_cap_pct_lbl') and self._cap_pct_lbl.winfo_exists():
                    self._cap_pct_lbl.config(text=f'{int(pct)}%')
        elif t == 'load_done':
            ok = obj.get('ok', False)
            model = obj.get('model','')
            if ok:
                self._cap_model_loaded = True
                self._cap_log_write(f'✓ {model} 就绪，模型已加载到显存', GREEN)
                self._cap_set_status(f'● {model} 就绪，可直接标注', GREEN)
                self._cap_set_progress(0)
                if hasattr(self, '_cap_pct_lbl') and self._cap_pct_lbl.winfo_exists():
                    self._cap_pct_lbl.config(text='')
                # 如果有待触发的标注任务，现在执行
                if hasattr(self, '_cap_pending_caption') and self._cap_pending_caption:
                    name, cb = self._cap_pending_caption
                    self._cap_pending_caption = None
                    if name == '__batch__':
                        self._caption_batch_real()
                    else:
                        self._do_caption_one(name, cb)
            else:
                self._cap_log_write(f'✗ {model} 加载失败，请查看上方错误', RED)
                self._cap_set_status(f'● {model} 加载失败', RED)
                self._cap_pending_caption = None
        elif t == 'caption_done':
            req_id  = obj.get('id','')
            result  = obj.get('result','')
            err_msg = obj.get('error','')
            cb = self._cap_pending.pop(req_id, None)
            if cb:
                cb(result, err_msg)
        elif t == 'proc_exit':
            self._cap_ready = False
            self._cap_set_status('● 服务已退出', TEXT_MUT)
            self._cap_log_write('服务进程已退出')

    def _cap_send(self, obj):
        import json as _json
        if not self._cap_proc or self._cap_proc.poll() is not None:
            self._cap_log_write('服务进程已退出，尝试重启...', YELLOW)
            self._cap_ready = False
            self._cap_start_service()
            return False
        try:
            self._cap_proc.stdin.write(_json.dumps(obj, ensure_ascii=False) + '\n')
            self._cap_proc.stdin.flush()
            return True
        except Exception as e:
            self._cap_log_write(f'发送失败: {e}', RED)
            return False

    # ── 标注操作 ─────────────────────────────

    def _on_cap_model_change(self):
        m = self._cap_model.get()
        if m == 'qwen':
            self._joy_sec.pack_forget()
            self._qwen_sec.pack(fill='x')
        else:
            self._qwen_sec.pack_forget()
            self._joy_sec.pack(fill='x')

    def _caption_current(self):
        """标注当前图"""
        if self.cur < 0 or not self.filtered:
            self._cap_log_write('请先选择一张图片'); return
        if not self._cap_ready:
            self._cap_log_write('服务启动中，请稍候...', YELLOW)
            self.after(600, self._caption_current)
            return
        model = self._cap_model.get()
        name  = self.filtered[self.cur]
        if self._cap_model_loaded:
            # 模型已在显存，直接标注
            self._cap_log_write(f'→ 直接标注 {name}（模型已在显存）')
            self._do_caption_one(name, self._on_caption_current_done)
        else:
            # 首次需要加载模型
            self._cap_set_status(f'● 加载 {model} 模型...', YELLOW)
            self._cap_send({'cmd': 'load', 'model': model})
            self._cap_pending_caption = (name, self._on_caption_current_done)

    def _on_caption_current_done(self, result, err):
        if err:
            self._cap_log_write(f'标注失败: {err}', RED); return
        if not result: return
        # 写入 Tag 编辑区并自动保存
        tags = [t.strip() for t in result.split(',') if t.strip()] if ',' in result \
               else [result.strip()]
        self.tag_panel.set_tags(tags)
        self._modified = True; self._set_mod(True)
        name = self.filtered[self.cur] if self.cur >= 0 else None
        if name:
            self._write(name, result)
        self._cap_log_write(f'✓ 标注完成并已保存', GREEN)
        self._cap_set_progress(1.0)
        self.after(1500, lambda: self._cap_set_progress(0))

    def _caption_batch(self):
        """批量标注当前筛选的图"""
        if not self.dirs.get('result') and not self.dirs.get('input'):
            messagebox.showwarning('提示', '请先选择输入图或结果图文件夹'); return
        if not self.filtered:
            self._cap_log_write('当前没有图片'); return
        if not self._cap_ready:
            self._cap_log_write('服务启动中，请稍候...', YELLOW)
            self.after(600, self._caption_batch)
            return

        overwrite = self._cap_overwrite.get()
        # 筛选出需要处理的图
        to_do = []
        for name in self.filtered:
            has_txt = name in self.txt_files
            if has_txt and overwrite == 'skip':
                continue
            # 优先用结果图，没有就用输入图
            img_path = self.files['result'].get(name) or self.files['input'].get(name)
            if img_path:
                to_do.append((name, img_path, has_txt))

        if not to_do:
            self._cap_log_write('没有需要处理的图片（全部已有TXT且选择了跳过）', YELLOW)
            return

        total = len(to_do)
        self._cap_log_write(f'开始批量标注 {total} 张图片...', ACCENT)
        self._cap_set_status(f'● 批量标注中 0/{total}', YELLOW)
        self._cap_set_progress(0)

        self._batch_stop  = False
        self._batch_done  = 0
        self._batch_total = total
        self._batch_queue = list(to_do)
        self._batch_overwrite = overwrite
        self._process_next_batch()

    def _process_next_batch(self):
        if self._batch_stop or not self._batch_queue:
            done = self._batch_done
            total = self._batch_total
            self._cap_log_write(f'✓ 批量完成：{done}/{total} 张', GREEN)
            self._cap_set_status(f'● 完成 {done}/{total}', GREEN)
            self._cap_set_progress(1.0)
            self.after(2000, lambda: self._cap_set_progress(0))
            self._update_global_tags()
            self._render_list()
            return

        name, img_path, has_txt = self._batch_queue.pop(0)

        def on_done(result, err):
            if err:
                self._cap_log_write(f'  ✗ {name}: {err}', RED)
                self._batch_done += 1
                self._next_batch_step()
                return
            if not result:
                self._batch_done += 1
                self._next_batch_step()
                return
            # 写入文件
            ow = self._batch_overwrite
            existing = self.txt_content.get(name, '')
            if ow == 'append' and existing:
                new_content = existing.rstrip(', ') + ', ' + result
            else:
                new_content = result
            self._write(name, new_content)
            self._batch_done += 1
            frac = self._batch_done / self._batch_total
            self._cap_set_progress(frac)
            self._cap_set_status(
                f'● 批量标注中 {self._batch_done}/{self._batch_total}', YELLOW)
            self._cap_log_write(
                f'  ✓ {name}  [{self._batch_done}/{self._batch_total}]', GREEN)
            # 如果是当前图，刷新 Tag 面板
            if self.cur >= 0 and self.filtered and self.filtered[self.cur] == name:
                tags = [t.strip() for t in new_content.split(',') if t.strip()]
                self.tag_panel.set_tags(tags)
                self._modified = False; self._set_mod(False)
            self._next_batch_step()

        self._do_caption_one(name, on_done, img_path=img_path)

    def _next_batch_step(self):
        # 稍作间隔避免 UI 卡顿
        self.after(50, self._process_next_batch)

    def _do_caption_one(self, name, callback, img_path=None):
        if img_path is None:
            img_path = self.files['result'].get(name) or self.files['input'].get(name)
        if not img_path or not img_path.exists():
            callback('', '找不到图片文件'); return

        self._cap_id += 1
        req_id = str(self._cap_id)
        self._cap_pending[req_id] = callback

        req_data = {
            'cmd':   'caption',
            'id':    req_id,
            'path':  str(img_path),
            'model': self._cap_model.get(),
            'mode':  self._cap_mode.get(),
        }
        if self._cap_model.get() == 'qwen':
            req_data['prompt']     = self._cap_prompt.get('1.0', 'end').strip()
            req_data['max_tokens'] = self._cap_max_tokens.get()
            req_data['thinking']   = False
        ok = self._cap_send(req_data)
        if not ok:
            self._cap_pending.pop(req_id, None)
            callback('', '服务未运行')
            return

        self._cap_log_write(f'  → 标注 {name}...')

        # 超时保护：120秒后如果还没回应，自动报错继续
        timeout_ms = 120_000
        def _timeout_check():
            if req_id in self._cap_pending:
                self._cap_log_write(f'  ⚠ {name} 超时（120s），跳过', YELLOW)
                cb = self._cap_pending.pop(req_id, None)
                if cb: cb('', '超时')
        self.after(timeout_ms, _timeout_check)

    def _caption_stop(self):
        """停止批量任务"""
        if hasattr(self, '_batch_stop'):
            self._batch_stop = True
            self._batch_queue = []
        self._cap_log_write('已停止', YELLOW)
        self._cap_set_status('● 已停止', YELLOW)

    def _install_deps(self):
        """一键安装/升级全部 AI 标注依赖"""
        import threading, subprocess

        self._cap_log_write('开始安装依赖，请稍候...', YELLOW)
        self._cap_set_status('● 安装依赖中...', YELLOW)

        steps = [
            ('PyTorch CUDA 12.4',
             [sys.executable, '-m', 'pip', 'install', '--quiet',
              '--disable-pip-version-check',
              'torch', 'torchvision',
              '--index-url', 'https://download.pytorch.org/whl/cu124']),
            ('huggingface_hub / accelerate / pillow / onnxruntime-gpu',
             [sys.executable, '-m', 'pip', 'install', '--quiet',
              '--disable-pip-version-check',
              'huggingface_hub', 'accelerate', 'pillow', 'numpy==1.26.4',
              'onnxruntime-gpu', '--upgrade']),
            ('transformers 最新版（Qwen3.5 需要）',
             [sys.executable, '-m', 'pip', 'install', '--quiet',
              '--disable-pip-version-check',
              'git+https://github.com/huggingface/transformers.git@main']),
        ]

        def run():
            ok = True
            for name, cmd in steps:
                self._cap_log_write(f'  安装 {name}...')
                try:
                    _cf = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=_cf)
                    if r.returncode == 0:
                        self._cap_log_write(f'  ✓ {name} OK', GREEN)
                    else:
                        self._cap_log_write(
                            f'  ✗ {name} 失败: {r.stderr[-200:]}', RED)
                        ok = False
                except Exception as e:
                    self._cap_log_write(f'  ✗ {name} 异常: {e}', RED)
                    ok = False

            if ok:
                self._cap_log_write(
                    '✓ 全部依赖安装完成！请关闭并重新打开 AI 标注面板。', GREEN)
                self._cap_set_status('● 依赖安装完成，请重启面板', GREEN)
            else:
                self._cap_log_write('⚠ 部分依赖安装失败，请检查网络后重试。', RED)
                self._cap_set_status('● 安装未完成', RED)

        threading.Thread(target=run, daemon=True).start()

if __name__ == '__main__':
    app = App()
    def _on_close():
        # 主窗口关闭时才停止服务进程
        if app._cap_proc and app._cap_proc.poll() is None:
            try:
                app._cap_proc.stdin.write('{"cmd":"quit"}\n')
                app._cap_proc.stdin.flush()
            except Exception:
                pass
            app._cap_proc.terminate()
        app.destroy()
    app.protocol('WM_DELETE_WINDOW', _on_close)
    app.mainloop()
