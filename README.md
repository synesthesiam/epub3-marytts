# Voice2json EPUB 3 MaryTTS Generator

Tool for building [MaryTTS](http://mary.dfki.de) voices from pre-aligned [audio e-books](https://www.readbeyond.it).

## Prerequisites

You will need Python 3.6, a Java JDK, Gradle (preferrably 4.x), and some extra tools:

```bash
$ sudo apt-get install sox praat speech-tools
```

## Installing

Clone this repository somewhere and run the `install.sh` script to create a Python virtual environment.
Afterwards, run `source .venv/bin/activate` to activate the environment.

## Running

Run the `prepare.py` script on your EPUB 3 audio e-book:

```bash
$ ./prepare.py /path/to/book.epub /path/to/output/
```

If all goes well, you will have a `marytts` directory in your output with this structure:

* marytts/
    * build/
        * text/
            * Transcriptions of each WAV file
    * wav/
        * WAV files

To build your voice, create the following two Gradle build files in `marytts`:

In `marytts/01-build.gradle` put:

```groovy
plugins {
  id "de.dfki.mary.voicebuilding.marytts-kaldi-mfa" version "0.3.6"
}

prepareForcedAlignment.wavDir = file("wav")
```

In `marytts/02-build.gradle` put:

```groovy

plugins {
    id 'de.dfki.mary.voicebuilding-legacy' version '5.4'
}

wav.srcDir = file("wav")

marytts {
    voice {
        name = 'my_voice'
        gender = 'male'
        language = 'en'
        region = 'US'
        domain = 'general'
        type = 'unit selection'
        description = 'A male English unit selection voice'
        samplingRate = 16000
        license {
            name = 'Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International'
            shortName = 'CC BY-NC-SA 4.0'
            url = 'http://creativecommons.org/licenses/by-nc-sa/4.0/'
        }
    }
}
```
Fill out the voice details appropriately.

Finally, you can build your voice with the following commands:

```bash
$ gradle -b 01-build.gradle convertTextToMaryXml
$ gradle -b 01-build.gradle processMaryXml
$ gradle -b 01-build.gradle prepareForcedAlignment
$ gradle -b 01-build.gradle unpackMFA
$ gradle -b 01-build.gradle runForcedAlignment
$ gradle -b 01-build.gradle convertTextGridToXLab

$ gradle -b 02-build.gradle build
```

In the end, you should have a zip file under `marytts/build/distributions`.
