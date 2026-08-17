"""
Script de diagnóstico de un solo uso: abre VDO.Ninja, hace clic en el botón
de invitación reutilizable, y guarda una captura de pantalla + el HTML
completo de la página para poder identificar el selector/URL real.

Uso:
    python debug_vdoninja.py
"""

from playwright.sync_api import sync_playwright

from config import load_config

config = load_config()

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False)
    context = browser.new_context()
    page = context.new_page()

    print(f"Abriendo {config.vdoninja.url} ...")
    page.goto(config.vdoninja.url, wait_until="domcontentloaded")

    print(f"Buscando y haciendo clic en: '{config.vdoninja.invite_button_text}' ...")
    page.get_by_text(config.vdoninja.invite_button_text, exact=False).first.click(timeout=10_000)

    page.wait_for_timeout(500)

    print("Buscando y haciendo clic en: 'GENERATE THE INVITE LINK' ...")
    page.get_by_text("GENERATE THE INVITE LINK", exact=False).first.click(timeout=10_000)

    page.wait_for_timeout(2000)

    # Guardar captura de pantalla
    page.screenshot(path="debug_vdoninja_after_click.png", full_page=True)
    print("Captura guardada en: debug_vdoninja_after_click.png")

    # Guardar el HTML completo
    with open("debug_vdoninja_after_click.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    print("HTML guardado en: debug_vdoninja_after_click.html")

    # Listar todos los inputs visibles y su valor
    print("\n--- INPUTS ENCONTRADOS ---")
    inputs = page.locator("input")
    count = inputs.count()
    print(f"Total de <input>: {count}")
    for i in range(count):
        try:
            el = inputs.nth(i)
            value = el.input_value(timeout=500)
            input_type = el.get_attribute("type") or "text"
            visible = el.is_visible()
            print(f"  [{i}] type={input_type} visible={visible} value={value[:120]!r}")
        except Exception as exc:
            print(f"  [{i}] (no se pudo leer: {exc})")

    # Buscar cualquier texto con "vdo.ninja" en todo el HTML
    print("\n--- OCURRENCIAS DE 'vdo.ninja' EN EL HTML ---")
    import re
    content = page.content()
    matches = re.findall(r"https?://vdo\.ninja/\?[^\s\"'<>]+", content)
    for m in set(matches):
        print(" ", m)

    print("\nLa ventana del navegador queda abierta. Ciérrala manualmente cuando termines de inspeccionar.")
    page.wait_for_event("close", timeout=0)
