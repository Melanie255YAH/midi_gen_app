from elevenlabs.client import ElevenLabs
from config import ELEVENLABS_API_KEY  # clé importée depuis ton fichier config.py

client = ElevenLabs(api_key=ELEVENLABS_API_KEY)  # clé passée explicitement ici


def get_all_voices():
    """
    Récupère toutes les voix disponibles sur le compte ElevenLabs.
    Retourne une liste de tuples (nom, voice_id).
    """
    voices = client.voices.get_all()
    return [(v.name, v.voice_id) for v in voices.voices]

def generate_eleven_audio(text: str, voice_id: str, output_path: str):
    """
    Génère un fichier audio à partir d’un texte et d’un voice_id ElevenLabs.

    Args:
        text (str): Le texte à synthétiser.
        voice_id (str): L’ID de la voix à utiliser.
        output_path (str): Chemin de sortie pour sauvegarder le fichier .mp3.
    """
    audio_stream = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id="eleven_multilingual_v1",
        text=text,
        output_format="mp3_44100"
    )

    with open(output_path, "wb") as f:
        for chunk in audio_stream:
            f.write(chunk)
