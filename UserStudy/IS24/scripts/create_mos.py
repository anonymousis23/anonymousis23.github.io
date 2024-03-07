from pathlib import Path
import os
import random

out_dir = Path("UserStudy/IS24/interfaces/mos")
audio_type_code = {
    'source': 'SR',
    'base': 'BS',
    'lite': 'LT'
}
random.seed(1234)

# ##########################################################################################################################
# MOS TEST
# ##########################################################################################################################

audio_samples_root = "UserStudy/IS24/Samples/MOS"
url_root = "../../Samples/MOS"

wav_list = []
_, audio_type_dirs, _ = next(os.walk(audio_samples_root))

for audio_type in audio_type_dirs:
    _, _, utterance_ids = next(os.walk(os.path.join(audio_samples_root, audio_type)))
    for utterance in utterance_ids:
        wav_dict = {}
        wav_dict['id'] = f"MOS_{audio_type_code[audio_type]}_{Path(utterance).stem}"
        wav_dict['wav_fpath'] = f"{os.path.join(url_root, audio_type, utterance)}"
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
        mos_test_fpath.write("\t\t\t\t\t" + "<source preload=\"none\" src=\"" + str(wav_fpath) + "\" type=\"audio/wav\" />" + "\n")
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