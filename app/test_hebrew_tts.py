import pyttsx3

engine = pyttsx3.init()
engine.setProperty("rate", 170)

voices = engine.getProperty("voices")
print("VOICES FOUND:")
for i, voice in enumerate(voices):
    print(i, voice.id)

engine.say("שלום, זה טסט בעברית")
engine.runAndWait()

print("DONE")