import flet as ft
import math
import random
import asyncio


def main(page: ft.Page):
    is_alive = True  # Add this flag
    # --- 1. Window Setup ---
    page.title = "Dev Assistant"
    page.window.width = 1000
    page.window.height = 700
    page.bgcolor = "#0C4A6E"  # Your dark theme background
    page.padding = 30
    page.theme_mode = ft.ThemeMode.DARK

    page.fonts = {
        "MidnightAngel": "Midnight Angel.ttf"
    }

    # --- 2. THE BACKGROUND ANIMATION ENGINE ---
    bg_stack = ft.Stack(expand=True)
    # Custom symbols drifting in the background
    symbols = ["{ }", "< />", "##", "0x00", "01", "git", "ARM", "/>", "sys", "CAN"]
    particles = []

    # Generate random floating symbols
    for _ in range(100):
        start_x = random.randint(0, 1500)
        start_y = random.randint(0, 1000)
        p = ft.Container(
            content=ft.Text(random.choice(symbols), size=random.randint(20, 30), color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD),
            left=start_x,
            top=start_y,
            opacity=random.uniform(0.04, 0.15),  # Extremely subtle against the dark blue
            data={
                "start_y": start_y,
                "spin_dir": random.choice([-1, 1]),
                "speed": random.uniform(0.5, 1.5),
                "offset": random.uniform(0, math.pi * 2)
            },
            animate_position=ft.Animation(500, ft.AnimationCurve.LINEAR),
            animate_rotation=ft.Animation(500, ft.AnimationCurve.LINEAR),
        )
        particles.append(p)
        bg_stack.controls.append(p)

    async def animate_background():
        """Asynchronous loop that continuously updates particle math without freezing the UI."""
        t = 0
        while is_alive:
            try:
                for p in particles:
                    p.top = p.data["start_y"] + math.sin(t * p.data["speed"] + p.data["offset"]) * 40
                    p.rotate = t * 0.05 * p.data["spin_dir"]

                # Double-check if the page is still there before updating
                if is_alive:
                    page.update()

                t += 0.5
                await asyncio.sleep(0.5)
            except:
                # If any error occurs (like closing the app), break the loop
                break

    # --- 3. Top Welcome Label ---
    welcome_label = ft.Row(
        controls=[
            ft.Text(
                "Welcome back, Bro",
                font_family="MidnightAngel",
                size=42,
                color=ft.Colors.WHITE
            )
        ],
        alignment=ft.MainAxisAlignment.CENTER
    )

    # --- 4. Central LMS / Task Panel ---
    main_panel = ft.Container(
        content=ft.Column(
            [
                # Changed to dark text to contrast your light blue panel
                ft.Text("LMS / Task Integration", size=24, color=ft.Colors.BLACK87, weight=ft.FontWeight.BOLD),
                ft.Text("Waiting for connection...", size=16, color=ft.Colors.BLACK54)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#73C8F7",
        border_radius=30,
        opacity=0.5,
        expand=True,
        alignment=ft.Alignment.CENTER,
        margin=ft.Margin.only(bottom=20, top=20)  # Added slight top margin to space from welcome text
    )

    # --- 5. The PHYSICALLY SLIDING Carousel ---
    nav_items = [
        {"src": "folder.png", "name": "folder"},
        {"src": "git.png", "name": "git"},
        {"src": "profile.png", "name": "profile"},
        {"src": "target.png", "name": "target"},
        {"src": "data_vault.png", "name": "data_vault"}
    ]

    current_index = 0
    icon_slots = []
    slot_lefts = [10, 110, 210, 310, 410]
    carousel_stack = ft.Stack(width=500, height=100)

    def update_carousel():
        for i, icon_container in enumerate(icon_slots):
            target_slot = (i - current_index) % 5
            icon_container.left = slot_lefts[target_slot]

            if target_slot == 2:
                icon_container.scale = 1.65
                icon_container.opacity = 1.0
            else:
                icon_container.scale = 1.0
                if abs(icon_slots[i].data - target_slot) > 2:
                    icon_container.opacity = 0.1
                else:
                    icon_container.opacity = 0.5

            icon_slots[i].data = target_slot
        page.update()

    def slide_left(e):
        nonlocal current_index
        current_index = (current_index - 1) % len(nav_items)
        update_carousel()

    def slide_right(e):
        nonlocal current_index
        current_index = (current_index + 1) % len(nav_items)
        update_carousel()

    def on_slot_click(e, item_index):
        nonlocal current_index
        clicked_slot = (item_index - current_index) % 5
        shift = clicked_slot - 2
        current_index = (current_index + shift) % len(nav_items)
        update_carousel()

    for i in range(5):
        nav_image = ft.Image(
            src=nav_items[i]["src"],
            width=80,
            height=80,
            fit=ft.BoxFit.CONTAIN
        )

        initial_slot = i
        icon_container = ft.Container(
            content=nav_image,
            left=slot_lefts[initial_slot],
            top=10,
            scale=1.65 if initial_slot == 2 else 1.0,
            opacity=1.0 if initial_slot == 2 else 0.5,
            data=initial_slot,

            animate_position=ft.Animation(350, ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_scale=ft.Animation(350, ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_opacity=ft.Animation(350, ft.AnimationCurve.EASE_OUT_CUBIC),

            on_click=lambda e, idx=i: on_slot_click(e, idx)
        )
        icon_slots.append(icon_container)
        carousel_stack.controls.append(icon_container)

    nav_bar = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_size=40, icon_color=ft.Colors.WHITE,
                              on_click=slide_left),
                carousel_stack,
                ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_size=40, icon_color=ft.Colors.WHITE,
                              on_click=slide_right)
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        bgcolor="#8DD3F8",
        height=100,
        border_radius=50,
        padding=ft.Padding.symmetric(horizontal=10),
        margin=ft.Margin.symmetric(horizontal=80)
    )

    # --- 6. Assemble the Master Page ---
    # Put the UI into its own column
    main_ui = ft.Column(
        [
            welcome_label,
            main_panel,
            nav_bar
        ],
        expand=True
    )

    # Stack the UI directly on top of the floating background animations
    master_stack = ft.Stack(
        controls=[
            bg_stack,
            main_ui
        ],
        expand=True
    )

    page.add(master_stack)

    # Fire up the background animation loop!
    page.run_task(animate_background)


# Run the app and grant Flet permission to access the icons folder
ft.run(main, assets_dir="Icons")