# -*- coding: utf-8 -*-
"""LANG-001: the app runs in English, Uzbek (Latin), Uzbek (Cyrillic) and Russian. Every
screen label resolves to a real string, Cyrillic Uzbek is the exact transliteration of the
Latin text, Russian is a full dictionary, and the phone voice gets a language it can speak."""
import re

from playwright.sync_api import sync_playwright

APP = "http://localhost:8765/"
CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


EXPECT = {
    "en": {"tab": "Home", "drive": "Drive", "settings": "Settings", "voice": "en"},
    "uz": {"tab": "Asosiy", "drive": "Haydash", "settings": "Sozlamalar", "voice": "uz"},
    "uz-Cyrl": {"tab": "Асосий", "drive": "Ҳайдаш", "settings": "Созламалар", "voice": "uz"},
    "ru": {"tab": "Главная", "drive": "Поездка", "settings": "Настройки", "voice": "ru"},
}

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    for lang, want in EXPECT.items():
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.add_init_script("localStorage.setItem('openai_key', 'test-key-never-sent');"
                                f"localStorage.setItem('app_lang', '{lang}');")
        page = context.new_page()
        page.goto(APP)
        page.wait_for_function("() => typeof I18N !== 'undefined' && !document.getElementById('home').classList.contains('hidden')")
        require(f"{lang}: the page is marked with its language", page.evaluate("() => document.documentElement.lang") == lang)
        require(f"{lang}: tab bar, Drive and Settings are in this language",
                page.locator("#tabHome .tab-lbl").text_content() == want["tab"]
                and page.evaluate("() => document.querySelector('#driveBtn .tile-lbl').textContent") == want["drive"]
                and page.evaluate("() => t('settings_title')") == want["settings"])
        missing = page.evaluate("""() => Object.keys(I18N.en).filter((k) => !(I18N[LANG] && I18N[LANG][k]))""")
        require(f"{lang}: every English key has a translation", missing == [])
        require(f"{lang}: the phone voice gets a language it speaks", page.evaluate("() => nativeLang()") == want["voice"])
        if lang in ("uz-Cyrl", "ru"):
            visible = page.evaluate("() => document.getElementById('home').innerText + document.getElementById('tabBar').innerText")
            require(f"{lang}: what the driver sees is written in Cyrillic", bool(CYRILLIC.search(visible)))
        context.close()

    # The Cyrillic dictionary is the transliteration of the Latin one, key by key.
    context = browser.new_context()
    page = context.new_page()
    page.goto(APP)
    page.wait_for_function("() => typeof I18N !== 'undefined'")
    same = page.evaluate("""() => Object.keys(I18N.uz).every((k) => I18N['uz-Cyrl'][k] === window.uzLatinToCyrillic(I18N.uz[k]))""")
    require("uz-Cyrl is generated from uz for every key", same)
    words = page.evaluate("""() => ["yo'l", "O'zbekiston", "G'alaba", "ma'lumot", "shahar", "choy", "yangi", "yuk", "yer",
        "ekran", "qishloq", "mahalla", "YO'Q", "OpenAI'ga", "Android'da", "#XavfsizHaydash", "km/soat", "{n} ta", "&nbsp;Rasm",
        "gpt-5.6/high", "Documents/pothole-frames", "speed_bump", "GPS", "#Uzbekiston"].map(window.uzLatinToCyrillic)""")
    require("the letter rules and the kept names, links and placeholders",
            words == ["йўл", "Ўзбекистон", "Ғалаба", "маълумот", "шаҳар", "чой", "янги", "юк", "ер",
                      "экран", "қишлоқ", "маҳалла", "ЙЎҚ", "OpenAI'га", "Android'да", "#ХавфсизҲайдаш", "км/соат",
                      "{n} та", "&nbsp;Расм", "gpt-5.6/high", "Documents/pothole-frames", "speed_bump", "GPS", "#Ўзбекистон"])
    placeholders = page.evaluate("""() => Object.keys(I18N.en).filter((k) => {
        const ph = (s) => (String(s).match(/\\{\\w+\\}/g) || []).sort().join();
        return ['uz', 'uz-Cyrl', 'ru'].some((l) => ph(I18N[l][k]) !== ph(I18N.en[k])); })""")
    require("every language keeps the same {placeholders} as English", placeholders == [])
    pure = page.evaluate("""() => { const P = window.StandaloneAPI.__pure; const out = {};
        for (const l of ['en', 'uz', 'uz-Cyrl', 'ru']) { localStorage.setItem('app_lang', l);
          out[l] = [P.acceptLanguage(), P.descriptionLanguage()]; } return out; }""")
    require("street names and AI descriptions follow the language",
            pure == {"en": ["en", None], "uz": ["uz,ru,en", "Uzbek (Latin script)"],
                     "uz-Cyrl": ["uz,ru,en", "Uzbek (Cyrillic script)"], "ru": ["ru,uz,en", "Russian"]})
    require("the selector offers all four",
            page.evaluate("() => [...document.querySelectorAll('#setLang option')].map((o) => o.value)") == ["en", "uz", "uz-Cyrl", "ru"])
    browser.close()

print("language checks passed")
