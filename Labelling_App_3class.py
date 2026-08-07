"""
Interactive tool for labeling FSCV voltammetry color plots.

Controls:
  Click+drag = Select time region
  0/1/2      = Label as Nothing/Serotonin/Uncertain
  ←/→        = Navigate between files
  X          = Delete mode (then 1-9 to delete specific label)
  D          = Delete ALL labels for current file
  B          = Toggle background subtraction
  J          = Jump to specific file
  Q          = Quit

Output: Saves labels to CSV after every action, saves labels in backup folder.
"""

# IMPORTS
# -----------------------------------------------

import os, shutil, datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.widgets import SpanSelector

# CONFIGURATION - Edit these to match your setup
# -----------------------------------------------
PLOT_DIR = r"C:\Users\julie\OneDrive - Imperial College London\data for 3 class annotations"
OUTPUT_CSV = r"C:\Users\julie\OneDrive - Imperial College London\3 class output\FSCV_Labels_June.csv"
BACKUP_DIR = r"C:\Users\julie\OneDrive - Imperial College London\3 class output\label_backups"
FSCV_HZ = 10                       # Sampling rate (frames per second)

# Label types: {id: (name, color)}
LABELS = {0: ("No Event", "blue"), 1: ("Spontaneous", "green"), 2: ("Stimulated", "red"), 3: ("Uncertain", "orange")}

# HELPER FUNCTIONS
# -----------------------------------------------
def get_files(d):
    """Get sorted list of data files from directory."""
    return sorted(f for f in os.listdir(d) if f.lower().endswith(('.npy', '.txt', '.csv')))

def load_arr(p):
    """Load FSCV data array from file. Returns 2D array (voltage x time)."""
    arr = np.load(p) if p.endswith('.npy') else np.loadtxt(p)
    return arr[np.newaxis, :] if arr.ndim == 1 else arr  # Ensure 2D

def bg_sub(arr, n=5):
    """Subtract baseline from first n seconds. Helps visualize signals."""
    nf = min(int(n * FSCV_HZ), arr.shape[1])  # Number of frames for baseline
    return arr - arr[:, :nf].mean(axis=1, keepdims=True) if nf > 0 else arr

def backup(csv):
    """Create timestamped backup of existing labels file."""
    if os.path.exists(csv):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        shutil.copy2(csv, f"{BACKUP_DIR}/backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv")

def load_df(csv):
    """Load labels CSV, creating empty DataFrame if doesn't exist."""
    if not os.path.exists(csv):
        return pd.DataFrame(columns=['index', 'plot_file', 'start_time', 'end_time', 'label', 'comment'])
    df = pd.read_csv(csv)
    # Ensure all required columns exist
    for c, d in [('index', 0), ('plot_file', ''), ('start_time', 0.0), ('end_time', 0.0), ('label', 0), ('comment', '')]:
        if c not in df.columns: df[c] = d
    df['comment'] = df['comment'].fillna('')
    return df

def save_df(df, csv):
    """Save labels DataFrame to CSV."""
    df.to_csv(csv, index=False)

# COLOURMAP CONFIGURATION (Pablo Prieto Roca, NeuroStemVolt 2026)
# -----------------------------------------------

class PLOT_SETTINGS:
    """Custom colourmap settings for FSCV data visualisation."""
    
    def __init__(self):
        # Custom colourmap for FSCV data visualisation
        # Author: Pablo Prieto Roca for NeuroStemVolt, 2026
        self.custom = self.get_continuous_cmap(
            ['#001524', '#002f5e', '#f4c300', '#a84900',
                '#64005f', '#21AE62', '#00751c', '#00ff00'],
            [0, 0.2478, 0.3805, 0.6555, 0.701, 0.7603, 0.7779, 1]
        )

    def get_norm(self, data, clim=None, vmax=None):
        """
        Color normalisation for the FSCV colour plot.

        The positive (oxidation) side always takes the full limit and the negative
        (reduction) side is fixed at -(2/3) of it. The top of the colorbar is therefore
        always higher in magnitude than the bottom (the range below 0.0 nA is smaller
        than above it), with 0.0 nA sitting at a constant ~0.4 up the colorbar.

        When a manual upper limit ``vmax`` is given it sets the top directly
        (e.g. top 1.0 -> bottom -0.67, top 14 -> bottom -9.33). With no manual limit
        the top auto-scales to max(|data|).

        Args:
            data: the FSCV data array.
            clim: optional positive limit for the auto path; defaults to max(|data|).
            vmax: optional manual upper limit (nA). Lower limit becomes -(2/3)*vmax.
        """
        if vmax is not None:
            # Manual top: bottom = -(2/3) * top  ->  0.0 sits at ~0.4 of the colormap.
            return mcolors.Normalize(vmin=-(2 / 3) * vmax, vmax=vmax)
        if clim is None:
            clim = np.nanmax(np.abs(data))
        # Auto top = clim, bottom = -(2/3)*clim: positive side always larger in magnitude.
        return mcolors.Normalize(vmin=-(2 / 3) * clim, vmax=clim)

    def get_continuous_cmap(self, hex_list, float_list=None):
        """Create a continuous colormap from hex colors and positions."""
        rgb_list = [self.rgb_to_dec(self.hex_to_rgb(i)) for i in hex_list]
        if float_list is None:
            float_list = list(np.linspace(0, 1, len(rgb_list)))

        cdict = dict()
        for num, col in enumerate(['red', 'green', 'blue']):
            col_list = [[float_list[i], rgb_list[i][num], rgb_list[i][num]]
                        for i in range(len(float_list))]
            cdict[col] = col_list
        cmp = mcolors.LinearSegmentedColormap(
            'my_cmp', segmentdata=cdict, N=256)
        return cmp

    def hex_to_rgb(self, value):
        """Convert hex color to RGB tuple."""
        value = value.strip("#")
        lv = len(value)
        return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

    def rgb_to_dec(self, value):
        """Convert RGB tuple to normalized [0-1] values."""
        return [v/256 for v in value]    

# MAIN LABELING CLASS
# -----------------------------------------------

class FSCVLabeler:

    """Interactive FSCV plot labeling application."""

    def __init__(self, review=None, unlabeled=False, multiple=False):
  
        # Initialise plot settings with custom colormap
        self.plot_settings = PLOT_SETTINGS()
        
        # Load all available files
        self.all_files = get_files(PLOT_DIR)
        assert self.all_files, f"No files in {PLOT_DIR}"
        
        # Backup existing labels and load them
        backup(OUTPUT_CSV)
        self.df = load_df(OUTPUT_CSV)
        
        # Apply filter based on review mode
        if unlabeled:
            # Files that don't appear in labels CSV
            self.files = [f for f in self.all_files if f not in set(self.df['plot_file'])]
            self.mode = "UNLABELED"
        elif multiple:
            # Files with more than one label entry
            counts = self.df.groupby('plot_file').size()
            multi = set(counts[counts > 1].index)
            self.files = [f for f in self.all_files if f in multi]
            self.mode = "MULTIPLE LABELS"
        elif review is not None:
            # Files containing a specific label type
            has_label = set(self.df[self.df['label'] == review]['plot_file'])
            self.files = [f for f in self.all_files if f in has_label]
            self.mode = LABELS[review][0]
        else:
            # No filter - show all files
            self.files, self.mode = list(self.all_files), None
        
        assert self.files, "No files match filter"
        
        # Initialise state
        self.idx = 0              # Current file index
        self.labels = []          # Labels for current file
        self.sel = None           # Selected region (start_time, end_time)
        self.bg = True            # Background subtraction on
        self.del_mode = False     # Delete mode off
        self.fig = self.ax = self.span = None  # Matplotlib objects (set in run())
    
    # Properties of current file 
    # -------------------------------------------------------------------------
    
    def cur_file(self):
        """Get filename of current file."""
        return self.files[self.idx]
    
    def cur_path(self):
        """Get full path to current file."""
        return os.path.join(PLOT_DIR, self.cur_file())
    
    def master_idx(self):
        """Get 1-based index in the complete file list (not filtered list)."""
        return self.all_files.index(self.cur_file()) + 1 if self.cur_file() in self.all_files else -1
    
    # Labels - load/save/add labels
    # -------------------------------------------------------------------------
    
    def load_labels(self):
        """Load labels for current file from DataFrame into self.labels list."""
        rows = self.df[self.df['plot_file'] == self.cur_file()]
        self.labels = [{'label': int(r['label']), 'start_time': float(r['start_time']), 
                        'end_time': float(r['end_time']), 'comment': str(r['comment'] or '')} for _, r in rows.iterrows()]
    
    def save_labels(self):
        """Save current file's labels to DataFrame and write to CSV."""
        # Remove old labels for this file
        self.df = self.df[self.df['plot_file'] != self.cur_file()]
        # Add new labels (if any)
        if self.labels:
            new = pd.DataFrame([{'index': self.master_idx(), 'plot_file': self.cur_file(), **L} for L in self.labels])
            self.df = pd.concat([self.df, new], ignore_index=True)
        save_df(self.df, OUTPUT_CSV)
    
    def add_label(self, lbl):
        """Add a new label for selected region (or entire file if no selection)."""
        arr = load_arr(self.cur_path())
        max_t = (arr.shape[1] - 1) / FSCV_HZ  # Max time in seconds
        
        # Use selection or default to entire file
        s, e = (self.sel if self.sel else (0.0, max_t))
        # Clamp to valid range
        s, e = max(0, min(s, max_t)), max(0, min(e, max_t))
        if s > e: s, e = e, s  # Ensure start < end
        
        self.labels.append({'label': lbl, 'start_time': s, 'end_time': e, 'comment': ''})
        self.save_labels()
        print(f"Labeled {'entire' if not self.sel else f'{s:.2f}s-{e:.2f}s'} as {LABELS[lbl][0]}")
        self.sel = None  # Clear selection
    
    # Navigation between files
    # -------------------------------------------------------------------------
    
    def goto(self, i):
        """Navigate to file at index i. Returns True if successful."""
        if 0 <= i < len(self.files):
            self.idx, self.sel, self.del_mode = i, None, False  # Reset state
            self.load_labels()
            return True
        return False
    
    def jump(self):
        """Interactive jump to file by number or name search."""
        inp = input("\nJump to (number/name/m:master): ").strip()
        if not inp: return False
        
        # Handle "m:123" format for index of entire file list
        if inp.lower().startswith('m:'):
            try:
                mi = int(inp[2:]) - 1
                if 0 <= mi < len(self.all_files) and self.all_files[mi] in self.files:
                    return self.goto(self.files.index(self.all_files[mi]))
            except: pass
            return False
        
        # Try as number
        try:
            return self.goto(int(inp) - 1)
        except: pass
        
        # Try as name search
        matches = [(i, f) for i, f in enumerate(self.files) if inp.lower() in f.lower()]
        if len(matches) == 1: return self.goto(matches[0][0])
        if matches:
            for j, (i, f) in enumerate(matches[:10]): print(f"  {j+1}. {f}")
            try: return self.goto(matches[int(input("Select: ")) - 1][0])
            except: pass
        return False
    
    
    # Visualisation
    # -------------------------------------------------------------------------
    
    def draw(self):
        """Redraw the current plot with labels and UI elements."""
        self.ax.clear()
        
        # Load and optionally background-subtract the data
        arr = load_arr(self.cur_path())
        if self.bg: arr = bg_sub(arr)
        nV, nT = arr.shape
        max_t = (nT - 1) / FSCV_HZ
        
        # Show color plot using Pablo's custom colourmap and normalisation
        norm = self.plot_settings.get_norm(arr)
        self.ax.imshow(arr, aspect='auto', cmap=self.plot_settings.custom, origin='lower', 
                       extent=[0, max_t, 0, nV], norm=norm)
        
        # Draw existing labels as colored overlays with text
        for i, L in enumerate(self.labels):
            c = LABELS[L['label']][1]
            self.ax.axvspan(L['start_time'], L['end_time'], color=c, alpha=0.3)
            self.ax.text((L['start_time']+L['end_time'])/2, nV*(0.95-i*0.08), 
                        f"#{i+1}: {LABELS[L['label']][0]} ({L['start_time']:.1f}-{L['end_time']:.1f}s)",
                        ha='center', va='top', fontsize=9, fontweight='bold', color='white',
                        bbox=dict(boxstyle='round', facecolor=c, alpha=0.8))
        
        # Draw current selection as yellow region
        if self.sel: self.ax.axvspan(*self.sel, color='yellow', alpha=0.4, hatch='//')
        
        # Build title with status info
        mode_str = f" [REVIEW: {self.mode}]" if self.mode else ""
        lbl_str = "NO LABELS" if not self.labels else f"{len(self.labels)} label{'s' if len(self.labels)>1 else ''}"
        ctrl = "DELETE: 1-9=del label, D=all, ESC=cancel" if self.del_mode else "[0/1/2/3]=Label [X]=Del [D]=All [B]=BG [J]=Jump [Q]=Quit"
        
        self.ax.set_title(f"[{self.idx+1}/{len(self.files)}] (Master: {self.master_idx()}/{len(self.all_files)}){mode_str}\n"
                         f"{self.cur_file()}\nBG: {'ON' if self.bg else 'OFF'} | {lbl_str}\n{ctrl}",
                         color='red' if self.del_mode else 'black')
        self.ax.set_xlabel("Time (s)"); self.ax.set_ylabel("Voltage Index")
        self.fig.canvas.draw_idle()
    
    # Event handlers
    # -------------------------------------------------------------------------
    
    def on_select(self, xmin, xmax):
        #Handle region selection via click+drag
        if xmin != xmax and not self.del_mode:
            self.sel = (min(xmin, xmax), max(xmin, xmax))
            self.draw()
    
    def on_key(self, event):
        #Handle keyboard input
        k = event.key
        
        # Delete mode: waiting for user to press 1-9 or cancel
        if self.del_mode:
            if k in '123456789' and int(k)-1 < len(self.labels):
                self.labels.pop(int(k)-1); self.save_labels(); self.del_mode = False
            elif k == 'd': self.labels = []; self.save_labels(); self.del_mode = False
            elif k in ['escape', 'x']: self.del_mode = False
            self.draw(); return
        
        # Normal mode
        if k in '0123': self.add_label(int(k)); self.goto(self.idx + 1); self.draw()
        elif k == 'right': self.goto(self.idx + 1); self.draw()
        elif k == 'left': self.goto(self.idx - 1); self.draw()
        elif k == 'x' and self.labels: self.del_mode = True; self.draw()
        elif k == 'd': self.labels = []; self.save_labels(); self.draw()
        elif k == 'b': self.bg = not self.bg; self.draw()
        elif k == 'j': plt.pause(0.1); self.jump(); self.draw()
        elif k in ['q', 'escape']: plt.close(self.fig)
    
    # Main run loop
    # -------------------------------------------------------------------------
    
    def run(self, start=0):
        """Start the interactive labeling session."""
        self.goto(start)
        self.fig, self.ax = plt.subplots(figsize=(14, 8))
        
        # Try to maximize window (works on Windows)
        try: plt.get_current_fig_manager().window.state('zoomed')
        except: pass
        
        # Set up region selector
        self.span = SpanSelector(self.ax, self.on_select, 'horizontal', useblit=True,
                                 props=dict(alpha=0.4, facecolor='yellow'), interactive=True)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        
        self.draw()
        plt.show()
        self._summary()
    
    def _summary(self):
        """Print session summary when quitting."""
        df = load_df(OUTPUT_CSV)
        unlabeled = len([f for f in self.all_files if f not in set(df['plot_file'])])
        multi = (df.groupby('plot_file').size() > 1).sum()
        print(f"\n{'='*50}\nSUMMARY: {len(df)} labels, {df['plot_file'].nunique()} files, {unlabeled} unlabeled, {multi} multi-label")
        for l, (n, _) in LABELS.items():
            c = len(df[df['label'] == l])
            if c: print(f"  {n}: {c}")


# MAIN 
# =====================

def main():
    """Main entry point - shows menu and starts labeler."""
    files = get_files(PLOT_DIR)
    df = load_df(OUTPUT_CSV) if os.path.exists(OUTPUT_CSV) else pd.DataFrame()
    labeled = set(df['plot_file']) if len(df) else set()
    unlabeled = [f for f in files if f not in labeled]
    
    # Show status
    print(f"FSCV Labeler | {len(files)} files | {len(labeled)} labeled | {len(unlabeled)} unlabeled")
    print("\n[Enter]=All [0/1/2/3]=Review label [u]=Unlabeled [m]=Multiple")
    
    # Get mode choice
    choice = input("Mode: ").strip().lower()
    review = int(choice) if choice in ['0', '1', '2', '3'] else None
    unlab, mult = choice == 'u', choice == 'm'
    
    # Create app with selected filter
    try:
        app = FSCVLabeler(review=review, unlabeled=unlab, multiple=mult)
    except AssertionError as e:
        print(f"Error: {e}"); return
    
    # Find first unlabeled file as default start point
    print(f"\n{len(app.files)} files in view")
    first_unlab = next((i for i, f in enumerate(app.files) if f not in labeled), 0)
    
    # Get start position
    start = input(f"Start at [{first_unlab+1}]: ").strip()
    start_idx = first_unlab
    if start:
        try: start_idx = int(start) - 1
        except: 
            m = [i for i, f in enumerate(app.files) if start.lower() in f.lower()]
            if m: start_idx = m[0]
    
    # Show controls and start
    print("\nControls: Drag=Select | 0/1/2/3=Label | ←/→=Nav | X=Delete mode | D=Delete all | B=BG | J=Jump | Q=Quit\n")
    app.run(start_idx)

if __name__ == "__main__":
    main()