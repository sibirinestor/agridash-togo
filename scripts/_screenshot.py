import asyncio
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8051/"
AUTH = ("admin", "togo2024")
OUT = "scripts/shots"

TABS = [
    ("tab-dash", "01_vue"),
    ("tab-crops", "02_cultures"),
    ("tab-macro", "03_macro"),
    ("tab-map", "04_carte"),
    ("tab-climate", "05_climat"),
    ("tab-forecast", "06_previsions"),
    ("tab-markets", "07_marches"),
    ("tab-risks", "08_risques"),
]


async def shoot(page, tab_id, name, theme):
    # click tab
    await page.click(f"#{tab_id}", timeout=15000)
    # wait for any plotly graph to finish
    await page.wait_for_timeout(3500)
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(800)
    path = f"{OUT}/{name}_{theme}.png"
    await page.screenshot(path=path, full_page=False)
    print("saved", path)


async def main():
    import os
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        context = await browser.new_context(
            viewport={"width": 1480, "height": 1000},
            http_credentials={"username": AUTH[0], "password": AUTH[1]},
        )
        page = await context.new_page()
        await page.goto(BASE)
        await page.wait_for_timeout(6000)

        # ---- LIGHT theme: all tabs ----
        for tab_id, name in TABS:
            try:
                await shoot(page, tab_id, name, "light")
            except Exception as e:
                print("ERR", name, e)

        # ---- DARK theme: toggle then revisit a few ----
        await page.click("#theme-toggle")
        await page.wait_for_timeout(1500)
        for tab_id, name in [TABS[0], TABS[3], TABS[5], TABS[7]]:
            try:
                await shoot(page, tab_id, name, "dark")
            except Exception as e:
                print("ERR", name, "dark", e)

        await browser.close()


asyncio.run(main())
