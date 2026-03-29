import pyttsx3

engine = pyttsx3.init()
engine.setProperty("rate", 170)

voices = engine.getProperty("voices")
print("VOICES FOUND:")
for i, voice in enumerate(voices):
    print(i, voice.id)

engine.say("Testing one two three")
engine.runAndWait()

print("DONE")