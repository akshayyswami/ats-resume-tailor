# Records docs/demo.gif. Run from the repo root: vhs docs/demo.tape
# Offline. The setup is hidden: it puts the plugin's bin/ on PATH, which is what installing the
# plugin does, and copies the invented persona's files and the fixtures into a scratch folder.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1100
Set Height 600
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "export PS1='$ ' PATH=$PWD/bin:$PATH"
Enter
Type "D=$(mktemp -d) && cp examples/persona/evidence.yaml examples/persona/resume.clean.md evals/fixtures/pdfs/two-column.pdf evals/fixtures/pdfs/one-column.pdf $D && cp evals/fixtures/resumes/number-not-in-cited-evidence.txt $D/resume.md && cd $D && clear"
Enter
Sleep 2s
Show

Type "ats-resume-tailor verify resume.md -e evidence.yaml"
Sleep 500ms
Enter
Sleep 4s

Type "ats-resume-tailor pdf-check two-column.pdf -s resume.clean.md"
Sleep 500ms
Enter
Sleep 5s

Type "ats-resume-tailor pdf-check one-column.pdf -s resume.clean.md"
Sleep 500ms
Enter
Sleep 5s
