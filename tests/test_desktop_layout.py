"""Real Tk geometry regressions, enabled explicitly on the Windows build runner."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import nullcontext


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('SRA_GUI_TESTS') == '1',
                     'Real Windows GUI checks run in the dedicated CI step.')
class LayoutTests(unittest.TestCase):
    @staticmethod
    def destroy_root(root):
        import tkinter as tk
        try:
            for timer in root.tk.call('after', 'info'):
                root.after_cancel(timer)
            root.destroy()
        except tk.TclError:
            pass

    def make_app(self, scaling):
        import tkinter as tk
        from src.desktop import ArchiveApp
        root = tk.Tk()
        root.tk.call('tk', 'scaling', scaling)
        app = ArchiveApp(root, restore=False)
        self.addCleanup(self.destroy_root, root)
        return root, app

    def assert_visible(self, widget, root):
        self.assertTrue(widget.winfo_ismapped(), widget)
        self.assertGreater(widget.winfo_width(), 10)
        self.assertGreater(widget.winfo_height(), 10)
        left, top = widget.winfo_rootx(), widget.winfo_rooty()
        right, bottom = left + widget.winfo_width(), top + widget.winfo_height()
        ancestor = widget.master
        while ancestor is not None:
            self.assertGreaterEqual(left, ancestor.winfo_rootx() - 1)
            self.assertGreaterEqual(top, ancestor.winfo_rooty() - 1)
            self.assertLessEqual(right, ancestor.winfo_rootx() + ancestor.winfo_width() + 1)
            self.assertLessEqual(bottom, ancestor.winfo_rooty() + ancestor.winfo_height() + 1)
            if ancestor is root:
                break
            ancestor = ancestor.master

    def test_primary_actions_fit_small_windows_at_100_150_200_percent(self):
        for scale in (96 / 72, 144 / 72, 192 / 72):
            root, app = self.make_app(scale)
            for size in ('720x480', '800x500', '1100x780'):
                root.geometry(size)
                for page, button in ((app.setup, app.analyze_button),
                                     (app.topic_page, app.classify_button),
                                     (app.paper_page, app.accept_button)):
                    with self.subTest(scaling=scale, size=size, page=page):
                        app.tabs.select(page)
                        root.update()
                        self.assert_visible(button, root)
                        self.assert_visible(app.stop_button, root)
            self.destroy_root(root)

    def test_setup_scrolls_to_form_bottom_without_moving_action_bar(self):
        root, app = self.make_app(192 / 72)
        root.geometry('720x480')
        root.update()
        viewport = app.setup_scroll.canvas
        before = app.analyze_button.winfo_rooty()
        self.assertGreater(float(viewport.cget('scrollregion').split()[3]), viewport.winfo_height())
        viewport.yview_moveto(1)
        root.update()
        self.assertAlmostEqual(viewport.yview()[1], 1, places=2)
        self.assertEqual(before, app.analyze_button.winfo_rooty())
        self.assert_visible(app.analyze_button, root)

    def test_wheel_scrolls_only_its_own_page_and_preserves_text_scrolling(self):
        root, app = self.make_app(192 / 72)
        root.geometry('720x480')
        root.update()
        viewport = app.setup_scroll.canvas
        start = viewport.yview()
        event = SimpleNamespace(widget=app.account_box.master, delta=-120, state=0, num=0)
        self.assertEqual(app.setup_scroll.wheel(event), 'break')
        root.update()
        self.assertGreater(viewport.yview()[0], start[0])
        unchanged = viewport.yview()
        event.widget = app.details
        self.assertIsNone(app.setup_scroll.wheel(event))
        self.assertEqual(viewport.yview(), unchanged)

    def test_delete_connection_requires_confirmation_and_clears_account_and_models(self):
        root, app = self.make_app(96 / 72)
        state = {'host_id': 'synthetic-host', 'active': 'synthetic-client', 'profiles': [
            {'client_id': 'synthetic-client', 'email': 'test@example.invalid', 'refresh_token': 'synthetic-token'}]}
        app.restore_accounts(state)
        app.models = [{'slug': 'mock', 'display_name': 'Mock'}]
        app.model_box.configure(values=['Mock'])
        app.model.set('Mock')
        with patch('src.desktop.messagebox.askyesno', return_value=False), patch.object(app, 'start') as start:
            app.delete_connection()
            start.assert_not_called()
        self.assertEqual(len(app.accounts), 1)
        def run_now(job, done):
            done(job())
        with patch('src.desktop.messagebox.askyesno', return_value=True), \
                patch('src.desktop.messagebox.showinfo'), \
                patch('src.desktop.load', return_value=state), \
                patch('src.desktop.session_lock', return_value=nullcontext()), \
                patch('src.chatgpt_auth.revoke_session', return_value=True), \
                patch('src.chatgpt_auth.save'), patch.object(app, 'start', side_effect=run_now):
            app.delete_connection()
        self.assertEqual(app.accounts, [])
        self.assertIsNone(app.account_id)
        self.assertEqual(app.account.get(), 'Neues Konto / Workspace')
        self.assertEqual(app.models, [])
        self.assertEqual(app.model.get(), '')

    def test_engine_choice_precedes_topics_and_hides_llm_controls_in_local_mode(self):
        root, app = self.make_app(96 / 72)
        root.update()
        self.assertEqual(app.engine.get(), 'Lokal')
        self.assertFalse(app.llm_panel.winfo_ismapped())
        app.engine.set('ChatGPT (LLM)')
        root.update()
        app.setup_scroll.canvas.yview_moveto(1)
        root.update()
        self.assertTrue(app.llm_panel.winfo_ismapped())
        app.engine.set('Lokal')
        root.update()
        self.assertFalse(app.llm_panel.winfo_ismapped())

    def test_manual_topics_can_be_entered_before_reading_any_pdf(self):
        root, app = self.make_app(96 / 72)
        app.add_topic()
        root.update()
        app.topic_name.set('Migration')
        app.topic_description.delete('1.0', 'end')
        app.topic_description.insert('1.0', 'Population movements')
        app.topic_keywords.set('migration, refugees')
        app.update_topic()
        self.assertIsNone(app.collection)
        self.assertEqual(app.draft_topics[0].name, 'Migration')
        self.assertEqual(app.draft_topics[0].keywords, ('migration', 'refugees'))

    def test_saved_archive_runs_without_requiring_keywords_or_topic_proposals_again(self):
        from pathlib import Path
        import tempfile
        from src.archive_store import ArchiveStore
        from src.archive_workflow import STRATEGIES
        from src.desktop_service import Topic
        from test_archive import make_pdf
        root, app = self.make_app(96 / 72)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_pdf(folder / 'a.pdf')
            ArchiveStore(folder).save_profile([Topic('Methods', 'Historical methods', keywords=('digital history',))], 'local')
            app.folder.set(str(folder))
            app.load_archive_profile()
            self.assertEqual(app.strategy.get(), STRATEGIES[0])
            def run_now(job, done):
                done(job())
            with patch.object(app, 'start', side_effect=run_now):
                app.analyze()
            self.assertTrue(app.ready)
            self.assertEqual(app.collection.papers[0].topic, 'Methods')
            self.assertTrue((folder / 'a.pdf').exists())

    def test_open_pdf_uses_selected_original_without_moving_it(self):
        from pathlib import Path
        from src.analysis import Metadata
        from src.desktop_service import MODES, Collection, Paper
        import tempfile
        root, app = self.make_app(96 / 72)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'a.pdf'
            source.write_bytes(b'synthetic')
            app.collection = Collection(folder, MODES[0], [Paper(source, Metadata('Title', 'Ada', '2024'), '', '')], [], [])
            app.assigned(app.collection)
            root.update()
            with patch('src.desktop.os.startfile') as launch:
                app.open_pdf()
            launch.assert_called_once_with(str(source))
            self.assertTrue(source.exists())

    def test_only_full_llm_offers_automatic_topic_proposals(self):
        from src.archive_workflow import STRATEGIES
        root, app = self.make_app(96 / 72)
        for engine in ('Lokal', 'Lokal mit LLM-Keywords'):
            app.engine.set(engine)
            self.assertNotIn(STRATEGIES[2], app.strategy_box.cget('values'))
        app.engine.set('ChatGPT (LLM)')
        self.assertIn(STRATEGIES[2], app.strategy_box.cget('values'))
        app.strategy.set(STRATEGIES[2])
        app.engine.set('Lokal')
        self.assertEqual(app.strategy.get(), STRATEGIES[1])

    def test_hybrid_keywords_need_explicit_adoption_and_rules_confirmation(self):
        from pathlib import Path
        import tempfile
        from src.archive_store import ArchiveStore
        from src.desktop_service import MODES
        from test_archive import make_pdf
        from test_processing import Reply
        root, app = self.make_app(96 / 72)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            make_pdf(folder / 'a.pdf')
            app.folder.set(str(folder))
            app.edit_rules()
            app.engine.set('Lokal mit LLM-Keywords')
            app.add_topic()
            root.update()
            app.topic_name.set('Methods')
            app.topic_description.delete('1.0', 'end')
            app.topic_description.insert('1.0', 'Digital history research methods')
            app.update_topic()
            app.account_id = 'synthetic'
            app.models = [{'slug': 'mock', 'display_name': 'Mock'}]
            app.model_box.configure(values=['Mock'])
            app.model.set('Mock')
            app.external.set(True)
            model = Reply({'topics': [{'name': 'Methods', 'keywords': ['digital history', 'text mining',
                        'historical research', 'digital humanities', 'archival methods'], 'reason': 'Draft'}]})
            def run_now(job, done):
                done(job())
            def with_client(mode, selected, slug, function):
                return function(model if mode == MODES[2] else None)
            with patch.object(app, 'start', side_effect=run_now), patch.object(app, 'with_client', side_effect=with_client):
                app.generate_keyword_rules()
                self.assertFalse(app.draft_topics[0].keywords)
                self.assertIsNone(ArchiveStore(folder).profile())
                app.apply_keyword_rules()
                self.assertIn('digital history', app.draft_topics[0].keywords)
                self.assertIsNone(ArchiveStore(folder).profile())
                app.analyze()
                root.update()
                app.classify()
            self.assertTrue(app.ready)
            self.assertEqual(app.collection.papers[0].topic, 'Methods')
            self.assertEqual(len(model.calls), 1)
            self.assertEqual(ArchiveStore(folder).profile()['workflow'], 'hybrid')


if __name__ == '__main__':
    unittest.main()
