import subprocess
p = subprocess.Popen(["netstat", "-an", "|", "grep", ":5000"], stdout=subprocess.PIPE)
output, err = p.communicate()
print  output
