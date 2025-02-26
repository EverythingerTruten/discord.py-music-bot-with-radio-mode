# discord.py-music-bot-with-radio-mode
This is a simple discord bot with standard commands like !play, !now-playing, !skip, !queue and !stop. I also added a !radio-mode command that when turned on makes the bot have a 50% chance to play a random .mp3 file from a specified nested directory.

By default the bot will look for subfolders inside of the folder you input as `RADIO_FILE_FOLDER`. If you want for it to just play the files from the main folder follow the instructions from the code at line 27.
I coded it this way by default so if you take the files from multiple sources and one has an overwhelming amount of files it doesn't just constantly play from this source. (For me I had some miscellanous voice lines from the internet but I also added the entirety of the radio host's voicelines from GTA V's Non Stop Pop)
