"""Capture all desktop pages with synthetic preview data on the Windows builder."""

from pathlib import Path
import sys
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import ImageGrab
from src.analysis import Metadata, TOPICS
from src.desktop import ArchiveApp
from src.desktop_service import Collection, MODES, Paper, Topic, assign

root = tk.Tk()
app = ArchiveApp(root, restore=False)
folder = Path.cwd() / 'Beispielordner'
paper = Paper(folder / 'Beispiel.pdf', Metadata('Digital History Methods', 'Ada Example', '2024'),
              '', 'Digital history and digital humanities.',
              analysis={'summary': 'Beispiel einer historischen Forschungsarbeit über digitale Methoden.',
                        'evidence': ['Digital history']})
collection = Collection(folder, MODES[0], [paper],
                        [Topic(name, ', '.join(words)) for name, words in TOPICS.items()], [])
app.prepared(collection)
app.assigned(assign(collection, {name: words for name, words in TOPICS.items()}))
output = Path('artifacts') / 'ui-preview'
output.mkdir(parents=True, exist_ok=True)
for number, page in enumerate((app.setup, app.topic_page, app.paper_page, app.log_page), 1):
    app.tabs.select(page)
    root.update()
    root.after(200)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(output / f'page-{number}.png')
root.destroy()
