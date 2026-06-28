import discord
import re
from datetime import datetime, timezone
from ui.base_elements import BaseAnnouncementView

class EventInputModal(discord.ui.Modal):
    """Modal interface for collecting complete event details including description and exact date/time."""
    
    def __init__(self, event_type: str, parent_view):
        super().__init__(title=f"{event_type} hinzufügen")
        self.event_type = event_type
        self.parent_view = parent_view

        # 1. Title Input
        self.event_title = discord.ui.TextInput(
            label="Titel",
            placeholder="z.B. Clanrunde grün, Skincontest Sommer, ...",
            required=True,
            max_length=50
        )
        # 2. Description Input
        self.event_desc = discord.ui.TextInput(
            label="Beschreibung",
            style=discord.TextStyle.paragraph,
            placeholder="Worum geht es bei dem Event? (max. 160 Zeichen)",
            required=True,
            max_length=160
        )
        # 3. Exact Date and Time Input
        self.event_datetime = discord.ui.TextInput(
            label="Datum & Uhrzeit (DD.MM.YYYY HH:MM)",
            placeholder="z.B. 15.10.2026 19:30",
            min_length=16,
            max_length=16,
            required=True
        )
        
        self.add_item(self.event_title)
        self.add_item(self.event_desc)
        self.add_item(self.event_datetime)

    async def on_submit(self, interaction: discord.Interaction):
        """Validates the inputs, calculates the weekday automatically, and stages the data."""
        raw_datetime = self.event_datetime.value.strip()
        
        # Validate and parse the explicit date/time format
        try:
            # Parse string into a timezone-aware datetime object
            parsed_dt = datetime.strptime(raw_datetime, "%d.%m.%Y %H:%M")
            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            # reset dropdown on error
            for child in self.parent_view.children:
                if isinstance(child, discord.ui.Select):
                    child.values.clear()

            await interaction.response.send_message(
                f"❌ **Fehler:** `{raw_datetime}` entspricht nicht dem Format `DD.MM.YYYY HH:MM` (z.B. 15.10.2026 19:30)!", 
                ephemeral=True
            )
            await interaction.message.edit(view=self.parent_view)
            return

        # German weekday translation dictionary
        german_weekdays = {
            0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 
            4: "Freitag", 5: "Samstag", 6: "Sonntag"
        }
        # Automatically calculate the weekday based on the parsed date (.weekday() returns 0-6)
        calculated_day = german_weekdays[parsed_dt.weekday()]

        event_data = {
            "title": self.event_title.value.strip(),
            "description": self.event_desc.value.strip(),
            "start_time": parsed_dt,             # Complete datetime object
            "day": calculated_day,                # Automatically calculated German weekday
            "type": self.event_type               # "Clanrunde" or "Normales Event"
        }
        
        # dropdown reset: clear the selected value to allow for new selections
        for child in self.parent_view.children:
            if isinstance(child, discord.ui.Select):
                child.values.clear()
        
        self.parent_view.items.append(event_data)
        await self.parent_view.update_preview(interaction)


class EventTypeSelect(discord.ui.Select):
    """Dropdown component allowing managers to select the classification of the event."""
    
    def __init__(self, parent_view):
        options = [
            discord.SelectOption(
                label="Clanrunde", 
                description="gemeinsame Runden mit einem Skinmotto", 
                emoji="👗"
            ),
            discord.SelectOption(
                label="Event", 
                description="Besondere Spiele, Events oder Gewinnspiele", 
                emoji="🎉"
            )
        ]
        super().__init__(
            placeholder="Wähle eine Event-Art aus...", 
            min_values=1, 
            max_values=1, 
            options=options, 
            row=0
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        """Triggers the detailed configuration input modal directly."""
        selected_type = self.values[0]
        await interaction.response.send_modal(EventInputModal(selected_type, self.parent_view))


class EventAnnounceView(BaseAnnouncementView):
    """Interactive event planning container that extends the base announcement view with event-specific logic."""
    
    def __init__(self, ctx, api_client, db_collection):
        super().__init__(ctx, api_client, db_collection, title_name="Event-Ankündigung")
        self.add_item(EventTypeSelect(self))

    def format_item_line(self, item) -> str:
        """formats a single added event entry for the live UI preview embed list."""
        emoji = "👗" if item["type"] == "Clanrunde" else "🎉"
        time_str = item["start_time"].strftime("%H:%M")
        return f"**{item['day']} ({item['start_time'].strftime('%d.%m.')}) um {time_str} Uhr**: {item['title']} *( {emoji} )*\n"

    def generate_final_message(self) -> str:
        """generates the final announcement text for Discord and in-game announcements, including all events with their details."""
        current_calweek = datetime.now(timezone.utc).isocalendar()[1]
        event_blocks = []
        has_clangame = False
        has_event = False

        for e in self.items:
            # Track if at least one of each type exists for announcement title
            if e["type"] == "Clanrunde":
                has_clangame = True
            elif e["type"] == "Event":
                has_event = True;
            
            day_upper = e["day"].upper()
            time_str = e["start_time"].strftime("%H:%M")
            date_str = e["start_time"].strftime("%d.%m.%Y")
            
            # formatted block for each event entry
            block = (
                f"{e['title']}\n"
                f"📅 {day_upper}, ({date_str}) um {time_str} Uhr\n"
                f"{e['description']}"
            )
            event_blocks.append(block)

        # title string generation based on the types of events
        title_parts = []
        if has_clangame:
            title_parts.append(f"CLANRUNDE {current_calweek}")
        if has_event:
            title_parts.append("NEUES EVENT")

        # join if both are there, otherwise just one
        title_text = " & ".join(title_parts)

        return (
            f"🍃 {title_text} 🍃\n\n"
            + "\n\n--------------------------------------------------\n\n".join(event_blocks) + "\n\n"
            + "Wir freuen uns auf euch! 🍃"
        )

    def prepare_db_documents(self, current_calweek: int) -> list:
        """converts the collected event entries into a list of structured MongoDB documents for database insertion"""
        documents = []
        for event in self.items:
            # clean up title for database storage (remove special characters, lowercase)
            tech_name = re.sub(r'[^a-zA-Z0-9]', '', event["title"]).lower()

            documents.append({
                "kw": current_calweek,
                "title": event["title"],
                "name": tech_name,
                "description": event["description"],
                "type": "clangame" if event["type"] == "Clanrunde" else "event",
                "start_time": event["start_time"],                       # MongoDB Date object
                "day": event["day"],                                     # computed GER weekday string
                "date_string": event["start_time"].strftime("%Y-%m-%d"), # date lookup string
                "time_string": event["start_time"].strftime("%H:%M"),    # time lookup string
            })
        return documents

    async def update_preview(self, interaction: discord.Interaction):
        """disable buttons and selects during confirmation stage to prevent edits, still allowing user to review final announcement."""
        if self.is_confirming:
            for child in self.children:
                if isinstance(child, discord.ui.Select):
                    child.disabled = True
                    
        await super().update_preview(interaction)