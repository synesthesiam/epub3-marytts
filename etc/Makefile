all:
	gradle -b 01-build.gradle convertTextToMaryXml
	gradle -b 01-build.gradle processMaryXml
	gradle -b 01-build.gradle prepareForcedAlignment
	gradle -b 01-build.gradle unpackMFA
	gradle -b 01-build.gradle runForcedAlignment
	gradle -b 01-build.gradle convertTextGridToXLab
	gradle -b 02-build.gradle build
