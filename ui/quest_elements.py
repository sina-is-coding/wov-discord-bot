import discord
import re
from datetime import datetime, timezone
from utils import get_prevday, get_full_day_name
from ui.base_elements import BaseAnnouncementView

class QuestInputModal(discord.ui.Modal):
    """Modal interface for collecting specific quest details from users."""
    
    def __init__(self, quest_type: str, parent_view):
        super().__init__(title=f"{quest_type}-Quest hinzufügen")
        self.quest_type = quest_type
        self.parent_view = parent_view

        # Text input fields for the modal UI
        self.quest_name = discord.ui.TextInput(
            label="Questname + Emojis",
            placeholder="z.B. killercircus 🃏🔥, pridebear 🐻🌈...",
            required=True
        )
        self.start_day = discord.ui.TextInput(
            label="Starttag",
            placeholder="z.B. Donnerstag, Montag, ...",
            required=True
        )
        
        self.add_item(self.quest_name)
        self.add_item(self.start_day)

    async def on_submit(self, interaction: discord.Interaction):
        """Processes the input data on submit."""
        eingabe_tag = self.start_day.value.strip()
        
        # Validate the day input using functions from utils.py
        full_day_name = get_full_day_name(eingabe_tag)
        prevday = get_prevday(full_day_name) if full_day_name else None
        
        # fail if the weekday input is invalid
        if prevday is None:
            await interaction.response.send_message(
                f"❌ **Fehler:** `{eingabe_tag}` ist kein gültiger deutscher Wochentag!", 
                ephemeral=True
            )
            return

        # Structure the payload data
        quest_data = {
            "name": self.quest_name.value.strip(),
            "day": full_day_name,
            "prevday": prevday,
            "type": self.quest_type
        }
        
        # Append data to the parent view and refresh the live preview interface
        self.parent_view.items.append(quest_data)
        await self.parent_view.update_preview(interaction)


class QuestAnnounceView(BaseAnnouncementView):
    """interactive view for managing quest announcements, extending the base announcement view."""
    
    def __init__(self, ctx, api_client, db_collection):
        super().__init__(ctx, api_client, db_collection, title_name="Quest-Ankündigung")

    def format_item_line(self, item) -> str:
        """formats a single quest entry into a structured line for the live preview."""
        emoji = "💰" if item["type"] == "Gold" else "💎"
        return f"• **{item['day']}**: {item['name']} ({emoji})\n"

    def generate_final_message(self) -> str:
        """generates the final announcement text for the community post based on collected quest entries."""
        # calculate current calendar week (ISO standard)
        current_calweek = datetime.now(timezone.utc).isocalendar()[1]
        quest_lines = []

        # generate lines for each quest entry, including day, name, and type
        for q in self.items:
            start_tag = q["day"]
            prev_day = q["prevday"]
            
            if q["type"] == "Gold":
                line = f"{start_tag.upper()}: {q['name']}-Goldquest (500 Gold 💰)"
            else:
                line = f"{start_tag.upper()}: {q['name']}-Gemquest (💎-Kosten werden am {prev_day.upper()} festgelegt)"
            quest_lines.append(line)

        # assemble the final public community post
        return (
            f"🍃 QUESTPLAN KW {current_calweek} 🍃\n\n"
            + "\n".join(quest_lines) + "\n\n"
            + "Wenn ihr mitmachen möchtet, achtet darauf, dass ihr das nötige Guthaben auf eurem Konto habt und ihr für die Quest abgestimmt habt! 🤞"
        )

    def prepare_db_documents(self, current_calweek: int) -> list:
        """transforms the collected quest entries into a list of structured MongoDB documents for database insertion."""
        documents = []
        for q in self.items:
            raw_input = q["name"]
            
            # clean the quest name to create a tech_name suitable for database storage (remove non-alphabetic characters and lowercase)
            tech_name = re.sub(r'[^a-zA-Z]', '', raw_input).lower() 
            type_emoji = "💰" if q["type"] == "Gold" else "💎"

            # structure the document for database insertion
            documents.append({
                "kw": current_calweek,
                "day": q["day"],
                "name": tech_name,
                "display_name": raw_input,
                "type": q["type"].lower(),
                "emoji": type_emoji
            })
        return documents

    # --- UI Button Interactions ---

    @discord.ui.button(label="Gold-Quest", style=discord.ButtonStyle.secondary, emoji="💰", row=0)
    async def add_gold_quest(self, interaction: discord.Interaction, button: discord.ui.Button):
        """triggers the pre-configured input modal for Gold quests."""
        await interaction.response.send_modal(QuestInputModal("Gold", self))

    @discord.ui.button(label="Gem-Quest", style=discord.ButtonStyle.primary, emoji="💎", row=0)
    async def add_gem_quest(self, interaction: discord.Interaction, button: discord.ui.Button):
        """triggers the pre-configured input modal for Gem quests."""
        await interaction.response.send_modal(QuestInputModal("Gem", self))