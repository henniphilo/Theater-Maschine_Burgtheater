-- Bulk-import Video Cues into QLab with Pixera OSC cue numbers.
--
-- Usage (from repo root):
--   osascript tools/qlab_import_video_cues.applescript "/path/to/videos" "data/qlab_cue_list_rz21.csv"
--
-- Prefer: make qlab-import VIDEO_DIR=... SOURCE=avatar

on run argv
	if (count of argv) < 2 then
		error "Usage: osascript qlab_import_video_cues.applescript VIDEO_FOLDER CSV_PATH"
	end if

	set videoFolderPOSIX to item 1 of argv
	set csvPathPOSIX to item 2 of argv

	set csvText to do shell script "cat " & quoted form of csvPathPOSIX
	set csvLines to paragraphs of csvText
	if (count of csvLines) < 2 then error "CSV ist leer: " & csvPathPOSIX

	set headerLine to item 1 of csvLines
	set numberIdx to my indexOfField(headerLine, "qlab_cue_number")
	set clipIdx to my indexOfField(headerLine, "clip_part")
	if numberIdx is 0 or clipIdx is 0 then
		error "CSV braucht Spalten qlab_cue_number und clip_part"
	end if

	set videoFiles to my listVideoFiles(videoFolderPOSIX)
	set createdCount to 0
	set skippedCount to 0
	set missingCount to 0

	tell application id "com.figure53.QLab.5"
		activate
		if (count of workspaces) is 0 then error "Kein QLab-Workspace geöffnet"
		tell front workspace
			repeat with i from 2 to count of csvLines
				set lineText to item i of csvLines
				if lineText is not "" then
					set rowFields to my splitCsvLine(lineText)
					if (count of rowFields) >= numberIdx and (count of rowFields) >= clipIdx then
						set targetCueNumber to item numberIdx of rowFields
						set clipPart to item clipIdx of rowFields
						set matchedFile to my findVideoFile(videoFiles, clipPart)
						if matchedFile is "" then
							set missingCount to missingCount + 1
						else
							try
								make type "video"
								set newCue to last item of (selected as list)
								set file target of newCue to matchedFile
								set the q number of newCue to targetCueNumber
								set the q name of newCue to clipPart
								set createdCount to createdCount + 1
							on error errMsg
								set skippedCount to skippedCount + 1
							end try
						end if
					end if
				end if
			end repeat
		end tell
	end tell

	return "Fertig: " & createdCount & " Cues angelegt, " & missingCount & " ohne Videodatei, " & skippedCount & " Fehler."
end run

on indexOfField(headerLine, fieldName)
	set oldDelims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to ","
	set headers to text items of headerLine
	set AppleScript's text item delimiters to oldDelims
	repeat with i from 1 to count of headers
		if (item i of headers) is fieldName then
			return i
		end if
	end repeat
	return 0
end indexOfField

on splitCsvLine(lineText)
	set oldDelims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to ","
	set rowFields to text items of lineText
	set AppleScript's text item delimiters to oldDelims
	return rowFields
end splitCsvLine

on listVideoFiles(folderPOSIX)
	set videoExtensions to {".mp4", ".mov", ".m4v", ".MP4", ".MOV", ".M4V"}
	set found to {}
	tell application "System Events"
		set folderItems to every file of folder folderPOSIX
		repeat with f in folderItems
			set fname to name of f
			repeat with ext in videoExtensions
				if fname ends with ext then
					set end of found to (folderPOSIX & "/" & fname)
					exit repeat
				end if
			end repeat
		end repeat
	end tell
	return found
end listVideoFiles

on normalizeName(rawName)
	set n to rawName
	set n to my replaceText(n, "_", "")
	set n to my replaceText(n, "-", "")
	set n to my replaceText(n, " ", "")
	return do shell script "python3 -c 'import sys; print(sys.argv[1].lower())' " & quoted form of n
end normalizeName

on replaceText(sourceText, findText, replaceWith)
	set oldDelims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to findText
	set parts to text items of sourceText
	set AppleScript's text item delimiters to replaceWith
	set joined to parts as string
	set AppleScript's text item delimiters to ""
	return joined
end replaceText

on findVideoFile(videoFiles, clipPart)
	set targetNorm to my normalizeName(clipPart)
	repeat with vf in videoFiles
		set baseName to do shell script "basename " & quoted form of vf
		set baseNoExt to my stripExtension(baseName)
		set fileNorm to my normalizeName(baseNoExt)
		if fileNorm is targetNorm then return POSIX file vf
		if fileNorm contains targetNorm then return POSIX file vf
		if targetNorm contains fileNorm then return POSIX file vf
	end repeat
	return ""
end findVideoFile

on stripExtension(fileName)
	set dotPos to 0
	repeat with i from (length of fileName) to 1 by -1
		if character i of fileName is "." then
			set dotPos to i
			exit repeat
		end if
	end repeat
	if dotPos > 0 then
		return text 1 thru (dotPos - 1) of fileName
	end if
	return fileName
end stripExtension
