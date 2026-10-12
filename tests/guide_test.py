# -*- coding: utf-8 -*-
"""The in-app guide opens from the header, shows every section in the chosen language as
plain text, and returns Home."""
from playwright.sync_api import sync_playwright

APP = "http://localhost:8765/"


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    for lang, title, first, safety in (
        ("en", "How to use", "1. Mount the phone", "8. Safety"),
        ("uz", "Qanday ishlatish", "1. Telefonni o'rnatish", "8. Xavfsizlik"),
    ):
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.add_init_script("localStorage.setItem('openai_key', 'test-key-never-sent');"
                                f"localStorage.setItem('app_lang', '{lang}');")
        page = context.new_page()
        page.goto(APP)
        page.wait_for_function("() => typeof renderGuide === 'function' && "
                               "!document.getElementById('home').classList.contains('hidden')")
        require(f"{lang}: the header button is labelled for screen readers",
                page.get_attribute("#guideBtn", "aria-label") == title)
        page.click("#guideBtn")
        page.wait_for_selector("#guide:not(.hidden)")
        heads = page.locator("#guideBody h2").all_text_contents()
        bodies = page.locator("#guideBody .meta").all_text_contents()
        require(f"{lang}: eight sections with a heading and text each",
                len(heads) == 8 and len(bodies) == 8 and all(len(b) > 80 for b in bodies)
                and heads[0] == first and heads[-1] == safety)
        require(f"{lang}: nothing renders as raw markup or an untranslated key",
                not any("&" in b or "<" in b or "guide_" in b for b in heads + bodies))
        require(f"{lang}: the guide is plain text, not HTML",
                page.evaluate("() => document.querySelectorAll('#guideBody *').length") == 17)
        page.click("#guideBack")
        page.wait_for_selector("#home:not(.hidden)")
        require(f"{lang}: Back returns Home", page.is_hidden("#guide"))
        context.close()
    browser.close()

print("guide checks passed")
