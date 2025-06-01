from pathlib import Path
import os
import random
import glob
import shutil

out_dir = Path("UserStudy/ASRU25/interfaces/mos")
out_dir_samples = Path("UserStudy/ASRU25/Samples/MOS")
audio_type_code = {
    'original': 'ORG',
    'wav_140la_nocl': 'WAV',
    'wav_140la_cl': 'WAV_CL',
    'wav_140la_cl_km': 'WAV_CL_KM',
}
random.seed(1234)

# ##########################################################################################################################
# MOS TEST
# ##########################################################################################################################

audio_samples_root = Path("/mnt/data1/waris/PSI-TAMU/Xarts_exp/recon_for_mos")
url_root = "https://anonymousis23.github.io/UserStudy/ASRU25/Samples/MOS"


wav_files = glob.glob(os.path.join(audio_samples_root, "original/**", "*.wav"), recursive=True)
sampled_wav_files = random.sample(wav_files, 15)
utterance_ids = [f"{Path(f).parent.parent.name}/wav/{Path(f).stem}" for f in sampled_wav_files]

wav_list = []
for audio_type in audio_type_code.keys():
    for utterance in utterance_ids:
        file_dir = (out_dir_samples / audio_type)
        file_dir.mkdir(parents=True, exist_ok=True)
        # utterance_copy_path = out_dir / audio_type / f"{utterance}.wav"
        utterance_source_path = audio_samples_root / audio_type / f"{utterance}.wav"
        shutil.copy(utterance_source_path, file_dir)

        utterance_stem = utterance.split('/')[-1]

        wav_dict = {}
        wav_dict['id'] = f"MOS_{audio_type_code[audio_type]}_{utterance_stem}"
        wav_dict['wav_fpath'] = f"{os.path.join(url_root, audio_type, utterance_stem)}.wav"
        wav_list.append(wav_dict)

random.shuffle(wav_list)
test_samples = len(wav_list)

mos_test_fpath = out_dir.joinpath("index.html")
mos_test_fpath = mos_test_fpath.open("w", encoding="utf-8")

num_sets = test_samples//5
for i in range(num_sets):
    mos_test_fpath.write("<h2>Set "+str(i+1)+"</h2>" + "\n")
    mos_test_fpath.write("<table class=\"tests\">" + "\n")
    mos_test_fpath.write("\t" + "<tbody>" + "\n")
    mos_test_fpath.write("\t\t" + "<tr>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td></td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td>(Level of distortion)</td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td>Imperceptible</td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td>Just perceptible, but not annoying</td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td>Perceptible and slightly annoying</td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td>Annoying, but not objectionable</td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td>Very annoying and objectionable</td>" + "\n")
    mos_test_fpath.write("\t\t" + "</tr>" + "\n")
    mos_test_fpath.write("\t\t" + "<tr>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td><strong>Q ID</strong></td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td><strong>&nbsp; &nbsp;Clip &nbsp;&nbsp;</strong></td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td><strong>Excellent</strong></td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td><strong>Good</strong></td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td><strong>Fair</strong></td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td><strong>Poor</strong></td>" + "\n")
    mos_test_fpath.write("\t\t\t" + "<td><strong>Bad</strong></td>" + "\n")
    mos_test_fpath.write("\t\t" + "</tr>" + "\n")

    for j in range(5):
        index = i*5+j
        wav_id = wav_list[index]['id']
        wav_fpath = wav_list[index]['wav_fpath']

        mos_test_fpath.write("\t\t" + "<tr>" + "\n")

        mos_test_fpath.write("\t\t\t" + "<td>Q"+str(index+1)+"</td>" + "\n")

        mos_test_fpath.write("\t\t\t" + "<td>" + "\n")
        mos_test_fpath.write("\t\t\t\t" + "<audio controls=\"controls\" preload=\"none\">" + "\n")
        mos_test_fpath.write("\t\t\t\t\t" + "<source preload=\"none\" src=\"" + str(wav_fpath) + "?raw=True" + "\" type=\"audio/wav\" />" + "\n")
        mos_test_fpath.write("\t\t\t\t" + "</audio>" + "\n")
        mos_test_fpath.write("\t\t\t" + "</td>" + "\n")

        mos_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"5\" /></td>" + "\n")
        mos_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"4\" /></td>" + "\n")
        mos_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"3\" /></td>" + "\n")
        mos_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"2\" /></td>" + "\n")
        mos_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"1\" /></td>" + "\n")

        mos_test_fpath.write("\t\t" + "</tr>" + "\n")
    mos_test_fpath.write("\t" + "</tbody>" + "\n")
    mos_test_fpath.write("</table>" + "\n")
mos_test_fpath.close()