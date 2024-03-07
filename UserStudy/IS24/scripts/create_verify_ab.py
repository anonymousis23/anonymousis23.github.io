from pathlib import Path
import os
import random

out_dir = Path("UserStudy/IS24/interfaces/verify")
audio_type_code = {
    'same': 'SME',
    'same_anon': 'SMA',
    'different': 'DIF'
}
random.seed(1234)

###########################################################################################################################
#
# VOICE SIMILARITY TEST (A B)
#
###########################################################################################################################

audio_samples_root = "UserStudy/IS24/Samples/Verifiability"
url_root = "UserStudy/IS24/Samples/Verifiability"


wav_list = []
wav_list = []
_, audio_type_dirs, _ = next(os.walk(audio_samples_root))

for audio_type in audio_type_dirs:
    utterances = open(os.path.join(audio_samples_root, audio_type, 'info.txt'), 'r').readlines()
    
    for uttr_pair in utterances:
        uttr_a, uttr_b = uttr_pair.strip().split('|')
        wav_dict = {}
        wav_dict['wav_fpath_a'] = f"{os.path.join(url_root, audio_type, uttr_a)}?raw=true"
        wav_dict['wav_fpath_b'] = f"{os.path.join(url_root, audio_type, uttr_b)}?raw=true"
        wav_dict['id'] = f"VS_{audio_type_code[audio_type]}_{Path(uttr_a).stem}_{Path(uttr_b).stem}"
        wav_list.append(wav_dict)
        

random.shuffle(wav_list)
test_samples = len(wav_list)

voice_similarity_test_fpath = out_dir.joinpath("index.html")
voice_similarity_test_fpath = voice_similarity_test_fpath.open("w", encoding="utf-8")

num_sets = test_samples//5
for i in range(num_sets):
    voice_similarity_test_fpath.write("<h2>Set "+str(i+1)+"</h2>" + "\n")
    voice_similarity_test_fpath.write("<table class=\"tests\">" + "\n")
    voice_similarity_test_fpath.write("\t" + "<tbody>" + "\n")
    voice_similarity_test_fpath.write("\t\t" + "<tr>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>QuestionID</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>&nbsp; &nbsp;Clip A &nbsp;&nbsp;</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>&nbsp; &nbsp;Clip B &nbsp;&nbsp;</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>Same or Not?</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>Not at all confident</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>&nbsp; &nbsp;| &nbsp;&nbsp;</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>Somewhat confident</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>&nbsp; &nbsp;| &nbsp;&nbsp;</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>Quite a bit confident</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>&nbsp; &nbsp;| &nbsp;&nbsp;</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>Extremely confident</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t" + "</tr>" + "\n")

    for j in range(5):
        index = i*5+j
        wav_id = wav_list[index]['id']
        wav_fpath_a = wav_list[index]['wav_fpath_a']
        wav_fpath_b = wav_list[index]['wav_fpath_b']

        voice_similarity_test_fpath.write("\t\t" + "<tr>" + "\n")

        voice_similarity_test_fpath.write("\t\t\t" + "<td>Q"+str(index+1)+"</td>" + "\n")

        voice_similarity_test_fpath.write("\t\t\t" + "<td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "<audio controls=\"controls\" preload=\"none\">" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<source preload=\"none\" src=\"" + str(wav_fpath_a) + "\" type=\"audio/wav\" />" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "</audio>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "</td>" + "\n")

        voice_similarity_test_fpath.write("\t\t\t" + "<td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "<audio controls=\"controls\" preload=\"none\">" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<source preload=\"none\" src=\"" + str(wav_fpath_b) + "\" type=\"audio/wav\" />" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "</audio>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "</td>" + "\n")

        voice_similarity_test_fpath.write("\t\t\t" + "<td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "<select class=\"form-control overall\" name=\"" + str(wav_id) + "_Answer_overall\">" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option selected=\"selected\" value=\"0\">- select one -</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"1\">Same</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"-1\">Different</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "</select>" + "\n")  
        voice_similarity_test_fpath.write("\t\t\t" + "</td>" + "\n")

        voice_similarity_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"1\" /></td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"2\" /></td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"3\" /></td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"4\" /></td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"5\" /></td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"6\" /></td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "<td style=\"text-align: center;\"><input name=\""+ str(wav_id) +"\" type=\"radio\" value=\"7\" /></td>" + "\n")

        voice_similarity_test_fpath.write("\t\t" + "</tr>" + "\n")
    voice_similarity_test_fpath.write("\t" + "</tbody>" + "\n")
    voice_similarity_test_fpath.write("</table>" + "\n")

voice_similarity_test_fpath.close()