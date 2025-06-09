# Political Misinformation Bot 
## CS 152, Spring 2025

## Group 8
Contributors: Sarah Barragan, Andrew Chen, Rhea Kapur, Raymond Obu, Teddy Zhang

## Links
Demo video: https://youtu.be/gVeRumsvAoI 
Poster: https://docs.google.com/presentation/d/1rOdz_VJr-9Pz5WO1cMxnH-9-WxY8MAFN/edit?usp=sharing&ouid=111795688893312742658&rtpof=true&sd=true'

# Usage:
1. `cs152bots-group8/DiscordBot $ python3 bot.py`
2. For users: DM `report` to the Group 8 mod bot:
4. For moderators: DM `moderate` to the Group 8 mod bot. Moderators may `skip` a report for personal reasons.
5. Type `report display` or `report summary` into `*-mod channel` to see overview or reports

# Overview:
Our bot funnels all messages through a classifier-LLM pipeline to automatically submit a report if needed. User reports go into the same queue, which is organized by how likely content is to cause imminent harm. Moderators, with LLM assistance, make decisions about each piece of content. 

![our presentation poster]([https://github.com/adam-p/markdown-here/raw/master/src/common/images/icon48.png](https://github.com/teddy-zhng/cs152bots-group8/blob/main/CS%20152%20Group%208%20Poster.pptx.pdf) "Presentation Poster")

