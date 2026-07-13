import discord
import asyncio
from datetime import datetime, timezone

class BaseAnnouncementView(discord.ui.View):
    def __init__(self, ctx, api_client, db_collection, title_name: str):
        super().__init__(timeout=1800) # 30 mins
        self.ctx = ctx
        self.api_client = api_client
        self.db_col = db_collection
        self.title_name = title_name
        self.items = []              
        self.is_confirming = False   # State-track: False = editing, True = confirmation

    def get_initial_embed(self) -> discord.Embed:
        """Generates the default empty embed shown before any item is added."""
        return discord.Embed(
            title=f"{self.title_name} vorbereiten",
            description=f"*Noch nichts hinzugefügt. Klicke auf die Buttons unten!*",
            color=discord.Color.green()
        )

    # --- Abstract Methods (Must be overridden by subclasses) ---
    def generate_final_message(self) -> str:
        """Builds the final text string for discord and ingame announcements."""
        raise NotImplementedError

    def format_item_line(self, item) -> str:
        """Formats a single item entry for the live preview embed list."""
        raise NotImplementedError

    def prepare_db_documents(self, current_calweek: int) -> list:
        """Converts the collected items into a list of MongoDB documents."""
        raise NotImplementedError

    async def update_preview(self, interaction: discord.Interaction):
        """Refreshes the interaction interface based on the current state."""
        if self.is_confirming:
            # confirmation stage: Show final text preview and lock inputs
            embed = discord.Embed(title=f"{self.title_name} vorbereiten", color=discord.Color.green())
            embed.description = (
                "**BITTE PRÜFEN:** So wird die Ankündigung gleich im Clan veröffentlicht:\n"
                "--------------------------------------------------\n"
                f"{self.generate_final_message()}\n"
                "--------------------------------------------------"
            )
            # Disable input buttons dynamically
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.row == 0:
                    child.disabled = True
            
            self.submit_announcement.label = "✅ Ja, jetzt final abschicken!"
            self.submit_announcement.style = discord.ButtonStyle.success
        else:
            # editing stage: Display live list of currently added items
            if not self.items:
                embed = self.get_initial_embed()
            else:
                embed = discord.Embed(title=f"{self.title_name} vorbereiten", color=discord.Color.green())
                embed_desc = ""
                for item in self.items:
                    embed_desc += self.format_item_line(item)
                embed.description = embed_desc

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Abbrechen", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Aborts the process and wipes the original message interface."""
        await interaction.response.edit_message(content="Vorgang abgebrochen.", embed=None, view=None)
        self.stop()

    @discord.ui.button(label="📢 Ankündigung abschicken", style=discord.ButtonStyle.success, row=1)
    async def submit_announcement(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.items:
            await interaction.response.send_message("Du musst mindestens einen Eintrag hinzufügen!", ephemeral=True)
            return

        # toggle confirmation state and show preview
        if not self.is_confirming:
            self.is_confirming = True
            await self.update_preview(interaction)
            return

        # Prevent double-click execution
        if getattr(self, "_is_processing", False):
            return
        self._is_processing = True

        # safety check against empty lists
        if not self.items:
            await interaction.response.send_message("❌ Fehler: Keine Daten zum Absenden gefunden.", ephemeral=True)
            self.stop()
            return

        message = self.generate_final_message()
        await interaction.response.edit_message(content="Sende Ankündigung & speichere Daten...", embed=None, view=None)
        
        try:
            # Status flags for the final consolidated feedback report
            api_status = "❌ Fehlgeschlagen"
            db_status = "❌ Fehlgeschlagen"

            # in game announcement via wolvesville api
            if self.api_client:
                try:
                    await self.api_client.send_announcement(message)
                    api_status = "✅ Erfolgreich"
                except Exception as api_err:
                    api_status = f"❌ API-Fehler ({api_err})"
            else:
                api_status = "⚠ Übersprungen (Kein API-Client konfiguriert)"

            # send announcement as discord message
            await self.ctx.send(message)
            
            # adding data to mongodb collection
            if self.db_col is not None:
                try:
                    current_calweek = datetime.now(timezone.utc).isocalendar()[1]
                    documents_to_insert = self.prepare_db_documents(current_calweek)
                    
                    if documents_to_insert:
                        await asyncio.to_thread(self.db_col.insert_many, documents_to_insert)
                        db_status = "✅ Erfolgreich"
                    else:
                        db_status = "❌ Fehler (Keine Daten extrahiert)"
                except Exception as db_err:
                    db_status = f"❌ DB-Fehler ({db_err})"
            else:
                db_status = "⚠ Übersprungen (Keine DB-Verbindung)"

            # final feedback report
            status_report = (
                f"# {self.title_name} - Ergebnisse:\n"
                f"**In-Game API:** {api_status}\n\n"
                f"**MongoDB:** {db_status}\n\n"
            )
            await self.ctx.send(status_report)

        except Exception as e:
            await self.ctx.send(f"❌ Kritischer Verarbeitungsfehler: {e}")

        self.stop()