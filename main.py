import os
import re
import subprocess
import sys
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI

from config import OPENAI_API_KEY
from utils.voice_generator import generate_eleven_audio, get_all_voices

# === Constantes et configurations de base ===
# Configuration du chemin du dossier principal pour sauvegarder les données
BASE_CONFIG_DIR = os.path.expanduser("~/Desktop/Configurations_MIDI")
os.makedirs(BASE_CONFIG_DIR, exist_ok=True)

# Initialisation du client OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Générateur Textuel + MIDI + Voix",
    layout="centered"
)
st.title("🎛️ Générateur de prompts textuels + MIDI + Voix")

# === Fonctions utiles ===
def execute_midi_script(script_path, output_midi_path):
    """
    Exécute un script Python MIDI en s'assurant que les imports et les chemins de sauvegarde sont corrects.
    Crée une copie temporaire pour éviter d'écraser le script original.
    """
    try:
        temp_script_path = script_path.replace(".py", "_temp.py")

        with open(script_path, "r") as f:
            py_code = f.read()

        # Ajoute les imports nécessaires si absents
        if "from mido" not in py_code and "import pretty_midi" not in py_code:
            py_code = "from mido import Message, MidiFile, MidiTrack, bpm2tempo, MetaMessage\n" + py_code

        # Remplace les chemins de sauvegarde pour que la sortie aille dans le bon dossier
        py_code = re.sub(
            r'mid\.save\(["\'].*?\.mid["\']\)',
            f'mid.save("{output_midi_path}")',
            py_code
        )
        py_code = re.sub(
            r'midi\.write\(["\'].*?\.mid["\']\)',
            f'midi.write("{output_midi_path}")',
            py_code
        )

        # Sauvegarde et exécute le script temporaire
        with open(temp_script_path, "w") as temp_file:
            temp_file.write(py_code)

        result = subprocess.run(
            ["python", temp_script_path],
            capture_output=True,
            text=True
        )

        return result.returncode, result.stdout, result.stderr

    except Exception as e:
        return -1, "", str(e)


# === Chargement des configurations ===
@st.cache_data
def load_factorial_config():
    """Charge et met en cache la configuration factorielle pour améliorer les performances."""
    try:
        df_config = pd.read_excel("data/factorial_table1.xlsx")
        df_config.columns = df_config.columns.str.strip().str.lower()
        return df_config
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement de la configuration : {e}")
        return None

# Utiliser un dictionnaire pour les options de voix pour un code plus propre
VOICES = {
    "OpenAI (neutre)": ["nova", "shimmer", "echo", "fable", "onyx", "alloy"],
    "ElevenLabs (humain)": None
}

# === Interface Streamlit ===
onglet1, onglet2 = st.tabs(["🛠️ Générateur", "🧾 Analyse factorielle"])

# Onglet 1: Générateur
with onglet1:
    st.subheader("✂️ Préparation de prompts & voix")
    
    df_config = load_factorial_config()

    if df_config is not None:
        last_modified = os.path.getmtime("data/factorial_table1.xlsx")
        #st.caption(f"🕒 Dernière modification : {datetime.fromtimestamp(last_modified).strftime('%d/%m/%Y à %H:%M:%S')}")

        st.markdown("### 🎛️ Sélection d'une configuration")
        config_options = [
            f"Config {i+1} | Temp={row['temperature']} / TopP={row['top_p']} / Erreur={row['autorisation_erreur']}"
            for i, row in df_config.iterrows()
        ]
        selected_index = st.selectbox(
            "📂 Choix d'une configuration :",
            options=range(len(config_options)),
            format_func=lambda i: config_options[i],
            key="select_config"
        )
        selected_row = df_config.iloc[selected_index]
        
        # Récupération des paramètres de la ligne sélectionnée
        temperature = st.slider("🌡️ Température", 0.0, 2.0, float(selected_row["temperature"]))
        top_p = st.slider("🔽️ top_p", 0.0, 1.0, float(selected_row["top_p"]))
        frequency_penalty = st.slider("📉 Pénalité de fréquence", 0.0, 2.0, float(selected_row.get("frequency_penalty", 0.0)))
        presence_penalty = st.slider("📈 Pénalité de présence", 0.0, 2.0, float(selected_row.get("presence_penalty", 0.0)))
        max_tokens = st.number_input("🔢 max_tokens", min_value=1, max_value=2048, value=int(selected_row.get("max_tokens", 500)))
        allow_error = st.checkbox("Autorisation à l'erreur", value=(selected_row.get("autorisation_erreur", "FAUX") == "VRAI"))

        st.markdown("---")

        st.markdown("### 📝 Consigne principale")
        consigne = st.text_area("Saisir la consigne pour ChatGPT", "")
        
        # Génération des prompts (TEXTE et MIDI)
        if st.button("🧠 Générer Prompt TEXTE"):
            error_text = "L'erreur est permise." if allow_error else ""
            prompt_text = (
                f"Répondez à la question suivante :\n{consigne}\n\n"
                f"{error_text}\n\n"
                f"Paramètres : Temp={temperature}, TopP={top_p}, "
                f"FrequencyPenalty={frequency_penalty}, PresencePenalty={presence_penalty}, MaxTokens={max_tokens}"
            )
            st.text_area("Prompt Texte", prompt_text, height=250)

        if st.button("🎵 Générer Prompt MIDI"):
            error_text = "L'erreur est permise." if allow_error else ""
            prompt_midi = (
                f"Générez un script Python créant 8 mesures MIDI avec pretty_midi ou mido.\n{consigne}\n\n"
                f"{error_text}\n"
                f"Paramètres : Temp={temperature}, TopP={top_p}, "
                f"FrequencyPenalty={frequency_penalty}, PresencePenalty={presence_penalty}, MaxTokens={max_tokens}"
            )
            st.text_area("Prompt MIDI", prompt_midi, height=250)

        st.markdown("---")

        st.markdown("### 🔊 Synthèse vocale")
        pasted_text = st.text_area("Coller un texte pour générer l'audio", "")
        voice_option = st.selectbox(
            "Méthode de synthèse :",
            ["API OpenAI (neutre)", "API ElevenLabs (humain)", "Lecture manuelle"]
        )

        if voice_option == "API OpenAI (neutre)":
            openai_voice = st.selectbox("Choisir la voix OpenAI :", VOICES["OpenAI (neutre)"])
            if st.button("🔈 Générer Audio OpenAI") and pasted_text.strip():
                with st.spinner("Synthèse avec OpenAI..."):
                    try:
                        audio_response = client.audio.speech.create(
                            model="tts-1",
                            voice=openai_voice,
                            input=pasted_text
                        )
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        audio_path = os.path.join(BASE_CONFIG_DIR, f"audio_openai_{timestamp}.mp3")
                        with open(audio_path, "wb") as f:
                            f.write(audio_response.content)
                        st.audio(audio_path)
                        st.download_button(
                            "📥 Télécharger l'audio",
                            data=open(audio_path, "rb").read(),
                            file_name=os.path.basename(audio_path),
                            mime="audio/mp3"
                        )
                        st.success("✅ Audio généré avec succès")
                    except Exception as e:
                        st.error(f"❌ Erreur : {e}")

        elif voice_option == "API ElevenLabs (humain)":
            try:
                voices = get_all_voices()
                selected_voice = st.selectbox("Choisir la voix ElevenLabs :", [v[0] for v in voices])
                if st.button("🔈 Générer Audio ElevenLabs") and pasted_text.strip():
                    with st.spinner("Synthèse avec ElevenLabs..."):
                        try:
                            voice_id = dict(voices)[selected_voice]
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            audio_path = os.path.join(BASE_CONFIG_DIR, f"audio_eleven_{timestamp}.mp3")
                            generate_eleven_audio(pasted_text, voice_id, audio_path)
                            st.audio(audio_path)
                            st.download_button(
                                "📥 Télécharger l'audio",
                                data=open(audio_path, "rb").read(),
                                file_name=os.path.basename(audio_path),
                                mime="audio/mp3"
                            )
                            st.success("✅ Audio généré avec succès")
                        except Exception as e:
                            st.error(f"❌ Erreur : {e}")
            except Exception as e:
                st.error(f"Erreur chargement voix ElevenLabs : {e}")
    else:
        st.warning("⚠️ Impossible de charger la configuration. Veuillez vérifier le fichier.")

# Onglet 2: Analyse factorielle
with onglet2:
    st.header("🧾 Analyse factorielle + Annotations")
    df = load_factorial_config()

    if df is not None:
        for idx, row in df.iterrows():
            config_name = f"Config_{idx+1}"
            config_dir = os.path.join(BASE_CONFIG_DIR, config_name)
            os.makedirs(config_dir, exist_ok=True)

            with st.expander(f"🧪 {config_name} | Temp={row['temperature']} | TopP={row['top_p']} | Erreur={row['autorisation_erreur']}"):
                
                st.markdown("### 📁 Upload de fichiers")
                col1, col2 = st.columns(2)
                with col1:
                    midi_file = st.file_uploader("🎵 Fichier MIDI", type="mid", key=f"midi_{idx}")
                    py_file = st.file_uploader("🐍 Script Python MIDI", type="py", key=f"py_{idx}")
                with col2:
                    audio_neutre = st.file_uploader("🎧 Voix API neutre", type="mp3", key=f"audio_api_{idx}")
                    audio_eleven = st.file_uploader("🎧 Voix ElevenLabs", type="mp3", key=f"audio_eleven_{idx}")
                    audio_cloned = st.file_uploader("🎧 Voix clonée", type="mp3", key=f"audio_cloned_{idx}")
                    audio_human = st.file_uploader("🎧 Voix humaine enregistrée", type="mp3", key=f"audio_human_{idx}")
                
                # Sauvegarde les fichiers uploadés
                uploaded_files = [
                    (midi_file, "midi.mid"), (py_file, "script.py"), (audio_neutre, "audio_api_neutre.mp3"),
                    (audio_eleven, "audio_eleven.mp3"), (audio_cloned, "audio_cloned.mp3"), (audio_human, "audio_humain.mp3")
                ]
                for file_obj, filename in uploaded_files:
                    if file_obj:
                        with open(os.path.join(config_dir, filename), "wb") as out_file:
                            out_file.write(file_obj.read())
                        st.success(f"✅ Fichier {filename} sauvegardé.")
                
                st.markdown("---")
                
                st.markdown("### 📋 Coller directement un script généré par ChatGPT")
                pasted_script = st.text_area(
                    f"💬 Colle ici le script Python généré pour {config_name}",
                    height=300,
                    key=f"pasted_script_{idx}"
                )

                if st.button(f"💾 Sauvegarder script.py pour {config_name}", key=f"save_script_{idx}"):
                    if pasted_script.strip():
                        script_path = os.path.join(config_dir, "script.py")
                        with open(script_path, "w") as f:
                            f.write(pasted_script)
                        st.success(f"✅ Script Python enregistré dans {script_path}")
                    else:
                        st.warning("⚠️ Veuillez coller un script avant de sauvegarder.")
                
                st.markdown("---")

                st.markdown("### 🧠 Annotations")
                col3, col4 = st.columns(2)
                with col3:
                    analysis = st.text_area("🔍 Analyse musicologique", key=f"analysis_{idx}")
                with col4:
                    comment = st.text_area("💬 Commentaire libre", key=f"comment_{idx}")

                if st.button(f"💾 Sauvegarder Annotations {config_name}", key=f"save_annotation_{idx}"):
                    save_path = os.path.join(config_dir, "annotations")
                    os.makedirs(save_path, exist_ok=True)
                    with open(os.path.join(save_path, "analyse_musicologique.txt"), "w") as f:
                        f.write(analysis or "")
                    with open(os.path.join(save_path, "commentaire.txt"), "w") as f:
                        f.write(comment or "")
                    with open(os.path.join(save_path, "parametres.txt"), "w") as f:
                        f.write(f"Temperature: {row['temperature']}\nTopP: {row['top_p']}\nErreur autorisée: {row['autorisation_erreur']}\n")
                    st.success(f"✅ Annotations sauvegardées pour {config_name}")

                st.markdown("---")

                st.markdown("### 🎼 Génération MIDI automatique")
                if st.button(f"🎼 Générer le MIDI pour {config_name}", key=f"generate_midi_{idx}"):
                    script_path = os.path.join(config_dir, "script.py")
                    midi_output_path = os.path.join(config_dir, f"config{idx+1}.mid")

                    if not os.path.exists(script_path):
                        st.warning("⚠️ Aucun script Python trouvé pour cette configuration.")
                    else:
                        with st.spinner("Génération du fichier MIDI..."):
                            returncode, stdout, stderr = execute_midi_script(script_path, midi_output_path)
                            if returncode != 0:
                                st.error(f"❌ Erreur dans le script :\n\n{stdout}\n\n{stderr}")
                            elif os.path.exists(midi_output_path):
                                st.audio(midi_output_path, format="audio/midi")
                                st.success(f"✅ MIDI généré : {midi_output_path}")
                            else:
                                st.warning("⚠️ Script exécuté, mais aucun fichier MIDI généré.")
    else:
        st.warning("⚠️ Impossible de charger la configuration. Veuillez vérifier le fichier.")