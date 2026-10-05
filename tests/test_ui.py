"""Checks for the window: buttons, keys, help overlay and tooltips (no real window needed).
Run:  python -m unittest discover -s tests"""

import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

import config
import main as ui


def key(k, char=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=char)


def click(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


class TestWindow(unittest.TestCase):
    def setUp(self):
        self.app = ui.App(show_help=False)

    def tearDown(self):
        pygame.quit()

    def button_centre(self, action):
        for rect, button in self.app.button_rects():
            if button["action"] == action:
                return rect.center
        raise AssertionError("no button " + action)

    def test_all_buttons_fit_in_the_window(self):
        rects = self.app.button_rects()
        self.assertGreaterEqual(len(rects), 12)
        for rect, _ in rects:
            self.assertLessEqual(rect.right, self.app.screen.get_width())
        self.app.act("split")
        for rect, _ in self.app.button_rects():
            self.assertLessEqual(rect.right, self.app.screen.get_width())

    def test_keys_and_buttons_do_the_same_thing(self):
        self.app.handle_event(key(pygame.K_SPACE, " "))
        self.assertTrue(self.app.paused)
        self.app.handle_event(click(self.button_centre("pause")))
        self.assertFalse(self.app.paused)

    def test_auction_details_open_and_close_from_the_keyboard(self):
        self.app.act("rush")
        for _ in range(10):
            self.app.sims[0].step()
        self.app.handle_event(key(pygame.K_a, "a"))
        self.assertTrue(self.app.auction_open)
        self.assertEqual(self.app.auction_index, len(self.app.sims[0].bus.auction_history) - 1)
        self.app.draw()
        self.app.handle_event(key(pygame.K_ESCAPE))
        self.assertFalse(self.app.auction_open)

    def test_rush_hour_button_creates_orders(self):
        before = len(self.app.sims[0].env.tasks)
        self.app.handle_event(click(self.button_centre("rush")))
        self.assertGreater(len(self.app.sims[0].env.tasks), before)

    def test_clicking_a_vehicle_fails_it(self):
        agent = self.app.sims[0].agents[0]
        view = ui.single_view()
        pixel = view.center(agent.position)
        self.app.handle_event(click(pixel))
        self.assertFalse(agent.is_alive())

    def test_split_screen_and_dispatcher_button(self):
        dispatcher_button = [b for _, b in self.app.button_rects() if b["action"] == "dispatcher"][0]
        self.assertFalse(dispatcher_button["enabled"])                      # auction mode: no dispatcher to switch
        self.app.handle_event(click(self.button_centre("split")))
        self.assertEqual(len(self.app.sims), 2)
        self.app.handle_event(click(self.button_centre("dispatcher")))
        self.assertFalse(self.app.sims[0].dispatcher.online)                # left side is the central one

    def test_help_overlay_closes_on_any_key_without_side_effects(self):
        self.app.help_open = True
        self.app.handle_event(key(pygame.K_SPACE, " "))
        self.assertFalse(self.app.help_open)
        self.assertFalse(self.app.paused)                                    # the key only closed the guide

    def test_question_mark_and_escape(self):
        self.app.handle_event(key(pygame.K_SLASH, "?"))
        self.assertTrue(self.app.help_open)
        self.app.help_open = False
        self.app.handle_event(key(pygame.K_ESCAPE))
        self.assertFalse(self.app.running)

    def test_drawing_works_in_every_mode(self):
        self.app.draw()
        self.app.help_open = True
        self.app.draw()
        self.app.help_open = False
        self.app.act("split")
        self.app.draw()


class TestTooltips(unittest.TestCase):
    def test_tooltips_describe_vehicles_orders_and_map(self):
        config.TASK_SPAWN_PROBABILITY = 0.0
        try:
            sim = ui.Simulation(seed=1, num_agents=3, strategy="AUCTION")
            task = sim.new_task()
            agent = sim.agents[0]
            self.assertIn("Vehicle A1", ui.tooltip_for(sim, agent.position)[0])
            self.assertIn("Order #%d" % task.task_id, ui.tooltip_for(sim, task.destination)[0])
            self.assertEqual(ui.tooltip_for(sim, sim.env.chargers[0])[0], "Charging station")
            self.assertEqual(ui.tooltip_for(sim, sorted(sim.env.obstacles)[0])[0], "Blocked road")
            sim.fail_agent(1)
            self.assertIn("FAILED", ui.tooltip_for(sim, agent.position)[0])
        finally:
            config.TASK_SPAWN_PROBABILITY = 0.08


if __name__ == "__main__":
    unittest.main()
