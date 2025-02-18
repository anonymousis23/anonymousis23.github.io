from pathlib import Path
import os
import random
import shutil

out_dir = Path("UserStudy/IS25/interfaces/verify")
out_dir.mkdir(parents=True, exist_ok=True)
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

audio_samples_root = "UserStudy/IS25/Samples/Verifiability"
url_root = "../../Samples/Verifiability"


wav_list = []
utterances = open(os.path.join(audio_samples_root, 'cmuspkrs_info.txt'), 'r').readlines()

for uttr_pair in utterances:
    speaker, uttr_a, uttr_b, factor_age, factor_gender, _, _ = uttr_pair.strip().split('|')
    shutil.copy(uttr_a, f"/mnt/nvme-data1/waris/publications/anonymousis23.github.io/UserStudy/IS25/Samples/Verifiability/{speaker}_{Path(uttr_a).name}")
    change_type = f"{factor_age}_{factor_gender}"

    wav_dict = {}
    uttr_a = f"{speaker}_{Path(uttr_a).name}"
    uttr_b = f"{Path(uttr_b).name}"
    wav_dict['wav_fpath_a'] = f"{os.path.join(url_root, uttr_a)}"
    wav_dict['wav_fpath_b'] = f"{os.path.join(url_root, uttr_b)}"
    wav_dict['id'] = f"VS_{change_type}_{Path(uttr_a).stem}_{Path(uttr_b).stem}"

    
    if random.random() < 0.5:
        wav_dict['wav_fpath_a'], wav_dict['wav_fpath_b'] = wav_dict['wav_fpath_b'], wav_dict['wav_fpath_a']
        wav_dict['id'] = f"VS_{change_type}_{Path(uttr_b).stem}_{Path(uttr_a).stem}"
        
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
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>Quality</strong></td>" + "\n")
    voice_similarity_test_fpath.write("\t\t\t" + "<td><strong>Speaker</strong></td>" + "\n")
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
        voice_similarity_test_fpath.write("\t\t\t\t" + "<select class=\"form-control overall\" name=\"" + str(wav_id) + "_quality_relative\">" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option selected=\"selected\" value=\"0\">- select one -</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"2\">A much better</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"1\">A better</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"0\">Similar Quality</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"-1\">B better</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"-2\">B much better</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "</select>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t" + "</td>" + "\n")


        voice_similarity_test_fpath.write("\t\t\t" + "<td>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "<select class=\"form-control overall\" name=\"" + str(wav_id) + "_speaker_choice\">" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option selected=\"selected\" value=\"0\">- select one -</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"1\">Same</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t\t" + "<option value=\"-1\">Different</option>" + "\n")
        voice_similarity_test_fpath.write("\t\t\t\t" + "</select>" + "\n")  
        voice_similarity_test_fpath.write("\t\t\t" + "</td>" + "\n")

        voice_similarity_test_fpath.write("\t\t" + "</tr>" + "\n")
    voice_similarity_test_fpath.write("\t" + "</tbody>" + "\n")
    voice_similarity_test_fpath.write("</table>" + "\n")

voice_similarity_test_fpath.close()