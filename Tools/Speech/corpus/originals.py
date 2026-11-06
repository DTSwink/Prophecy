"""Original scenes written for Prophecy's world (no external source). Hand-annotated tags.
Format: (category, mood, [(speaker_id, gender, role)], [(speaker_id, tags, english)])
Tag policy: casual talk mostly untagged or mild; strong tags only for real conflict, fear or grief.
"""
S = []
def scene(cat, mood, spk, lines): S.append(dict(category=cat, mood=mood, speakers=spk, lines=lines))

# ---------------- bargaining ----------------
scene('bargaining', 'light', [('S1', 'm', 'merchant'), ('S2', 'f', 'buyer')], [
 ('S1', '[warmly]', 'Good morning! Fresh apples, picked at dawn. Two coins a basket.'),
 ('S2', '', 'Two coins? They look a little bruised to me.'),
 ('S1', '[chuckles]', 'Bruised? Those are freckles. Apples have freckles too.'),
 ('S2', '[amused]', 'Then the freckles cost one coin, and the apples another.'),
 ('S1', '', 'Ah, you are a hard woman. One and a half, and I add a pear.'),
 ('S2', '', 'One coin and the pear, and I come back tomorrow.'),
 ('S1', '[sighs]', 'Every day you come back, and every day I lose money. Fine. One coin.'),
 ('S2', '[warmly]', 'You never lose money. Thank you, old friend.'),
])
scene('bargaining', 'tense', [('S1', 'm', 'smith'), ('S2', 'm', 'mercenary')], [
 ('S2', '', 'How much for the long blade on the wall?'),
 ('S1', '', 'Forty silver. Good steel, folded twelve times.'),
 ('S2', '[skeptical]', 'Forty? I could buy a horse for forty.'),
 ('S1', '', 'Then ride the horse into battle and see how it cuts.'),
 ('S2', '', 'Twenty-five. The hilt is plain and the guard is too short.'),
 ('S1', '[annoyed]', 'The guard is exactly as long as it should be. Thirty-five, not one coin less.'),
 ('S2', '', 'Thirty, and I tell every soldier in the camp where I bought it.'),
 ('S1', '', '...Thirty-two. And you sharpen it here, not at that thief across the square.'),
 ('S2', '[chuckles]', 'Deal.'),
])
scene('bargaining', 'light', [('S1', 'f', 'innkeeper'), ('S2', 'm', 'traveller'), ('S3', 'f', 'traveller')], [
 ('S2', '', 'We need a room for two nights, and a stall for the mule.'),
 ('S1', '', 'Room is six a night. The mule is two, he eats more than you.'),
 ('S3', '[amused]', 'That is true, he does.'),
 ('S2', '', 'Could we do ten for everything if we help in the kitchen?'),
 ('S1', '[curious]', 'Can you cook?'),
 ('S3', '', 'He can burn water. I can cook.'),
 ('S1', '[laughs]', 'Then she works, and you carry wood. Ten for everything.'),
 ('S2', '', 'Fair enough. Where do I find the axe?'),
])
scene('bargaining', 'calm', [('S1', 'm', 'farmer'), ('S2', 'm', 'farmer')], [
 ('S1', '', 'My cow for your two goats and the cart.'),
 ('S2', '', 'Your cow is old. The cart is almost new.'),
 ('S1', '', 'She is old, but she still gives milk every morning. Your goats eat my fence.'),
 ('S2', '[thoughtful]', 'Hmm. The cart stays with me. Cow for the two goats and a sack of grain.'),
 ('S1', '', 'Two sacks.'),
 ('S2', '', 'One sack, and I lend you the cart at harvest.'),
 ('S1', '', 'All right. Shake on it.'),
])
scene('bargaining', 'tense', [('S1', 'f', 'captain'), ('S2', 'm', 'sellsword'), ('S3', 'm', 'sellsword')], [
 ('S1', '', 'We pay ten silver a man for the week. Food included.'),
 ('S2', '', 'Ten? The road to the north is full of raiders.'),
 ('S3', '', 'Last month the lord paid twenty.'),
 ('S1', '[firmly]', 'Last month the lord lost half his men. I am not him.'),
 ('S2', '', 'Fifteen, and we keep whatever we take from the raiders.'),
 ('S1', '', 'Twelve, you keep the weapons, the coin goes to the village.'),
 ('S3', '[quietly]', 'Take it. The village fed us last winter.'),
 ('S2', '[sighs]', 'Twelve then. But the food better be warm.'),
])
scene('bargaining', 'light', [('S1', 'f', 'herbalist'), ('S2', 'f', 'customer')], [
 ('S2', '', 'Do you have anything for a cough? My son has been coughing for three days.'),
 ('S1', '[warmly]', 'Honey, thyme and a little pine resin. Boil it, let him breathe the steam.'),
 ('S2', '', 'How much is it?'),
 ('S1', '', 'Three coins, but bring the jar back and the next one is two.'),
 ('S2', '', 'I only have two now.'),
 ('S1', '[softly]', 'Then pay me two now and the rest when he is well.'),
 ('S2', '[warmly]', 'Thank you. Really.'),
])

# ---------------- storytelling ----------------
scene('storytelling', 'warm', [('S1', 'm', 'old soldier'), ('S2', 'm', 'young recruit'), ('S3', 'f', 'barmaid')], [
 ('S1', '[thoughtful]', 'Forty winters ago we held the bridge at the black river. Nine of us. Nine.'),
 ('S2', '[curious]', 'Against how many?'),
 ('S1', '', 'Nobody counted. When the sun came up, the river was the colour of wine.'),
 ('S3', '', 'Every year the river gets redder and the enemy gets bigger.'),
 ('S1', '[chuckles]', 'Every year my knees get older, so the story must get stronger.'),
 ('S2', '', 'And then what happened?'),
 ('S1', '', 'Then the rain came. Three days of rain. And on the fourth morning, they were gone.'),
 ('S2', '', 'Just gone?'),
 ('S1', '[softly]', 'Just gone. Sometimes the river decides who wins, boy. Not the sword.'),
])
scene('storytelling', 'eerie', [('S1', 'f', 'grandmother'), ('S2', 'f', 'child'), ('S3', 'm', 'child')], [
 ('S1', '[softly]', 'In the forest beyond the mill, there is a stone that sings at night.'),
 ('S3', '', 'Stones cannot sing.'),
 ('S1', '', 'This one can. Low and slow, like a mother humming to her baby.'),
 ('S2', '[curious]', 'Did you hear it?'),
 ('S1', '', 'Once. I was younger than you. I followed the song until the trees were black around me.'),
 ('S3', '[nervous]', 'And then?'),
 ('S1', '', 'Then your grandfather found me, asleep against the stone, with frost in my hair.'),
 ('S2', '', 'Was the stone angry?'),
 ('S1', '[warmly]', 'No, little one. I think it was lonely. Now go to sleep.'),
])
scene('storytelling', 'funny', [('S1', 'm', 'merchant'), ('S2', 'm', 'merchant'), ('S3', 'f', 'merchant'), ('S4', 'm', 'guard')], [
 ('S1', '', 'Did I ever tell you about the goat that crossed the mountains with me?'),
 ('S3', '[amused]', 'Only twice this week.'),
 ('S1', '', 'Then this is the third time. She ate my map on the first day.'),
 ('S2', '[chuckles]', 'So how did you find the pass?'),
 ('S1', '', 'I followed the goat. She knew the way better than the map.'),
 ('S4', '', 'And where is this clever goat now?'),
 ('S1', '[sighs]', 'She married a shepherd on the other side. I came back alone.'),
 ('S3', '[laughs]', 'Married!'),
 ('S1', '', 'In her way. She never looked back, not even once.'),
])
scene('storytelling', 'heavy', [('S1', 'm', 'veteran'), ('S2', 'f', 'healer')], [
 ('S2', '', 'You never talk about the siege.'),
 ('S1', '', 'There is not much to say. We were hungry, then we were very hungry.'),
 ('S2', '[softly]', 'Your brother was there.'),
 ('S1', '[sighs]', 'He was. He gave me his bread on the last night. Said he was not hungry.'),
 ('S2', '', 'Was he?'),
 ('S1', '[sad]', 'He was the hungriest man I ever knew. ...He did not see the morning.'),
 ('S2', '[softly]', 'I am sorry.'),
 ('S1', '', 'Do not be. Every morning I see is a little bit his.'),
])
scene('storytelling', 'adventure', [('S1', 'f', 'scout'), ('S2', 'm', 'captain'), ('S3', 'm', 'soldier')], [
 ('S1', '', 'We went in through the old drain. Water up to our knees, rats everywhere.'),
 ('S3', '[disgusted]', 'Rats. Of course there were rats.'),
 ('S1', '', 'At the end, a gate. Rusted shut. Torven pulled so hard his face went purple.'),
 ('S2', '', 'Did it open?'),
 ('S1', '[amused]', 'No. The wall next to it fell down instead.'),
 ('S3', '[laughs]', 'That sounds like Torven.'),
 ('S1', '', 'So we walked into the cellar through the hole, and the guards were asleep on the wine barrels.'),
 ('S2', '', 'And the key?'),
 ('S1', '[confident]', 'Around the fat one\'s neck. He never woke up.'),
])

# ---------------- dispute ----------------
scene('dispute', 'heated', [('S1', 'm', 'guard'), ('S2', 'm', 'farmer'), ('S3', 'f', 'farmer wife')], [
 ('S1', '', 'Stop. Nobody passes the gate after dark.'),
 ('S2', '', 'We live on the other side! Our children are inside.'),
 ('S1', '', 'Rules are rules. Come back at dawn.'),
 ('S3', '[angry]', 'Our son is six years old and alone in that house!'),
 ('S1', '[firmly]', 'And if I open this gate for you, I open it for everyone.'),
 ('S2', '[angry]', 'Then open it for everyone! Who is out there? Nobody!'),
 ('S1', '', '...Fine. Quickly. And if the captain asks, you climbed the wall.'),
 ('S3', '[softly]', 'Thank you. Thank you.'),
])
scene('dispute', 'heated', [('S1', 'm', 'brother'), ('S2', 'm', 'brother'), ('S3', 'f', 'mother')], [
 ('S1', '', 'Father left the mill to me. Everyone knows it.'),
 ('S2', '[annoyed]', 'Father left the mill to both of us, and you know it.'),
 ('S1', '', 'You were gone for six years! Six years, and now you want half?'),
 ('S2', '[angry]', 'I was gone because he sent me away! To pay his debts!'),
 ('S3', '[firmly]', 'Enough. Both of you, sit down.'),
 ('S1', '', 'Mother, he...'),
 ('S3', '', 'I said sit. Your father wanted you to work it together. Not to fight over it like dogs.'),
 ('S2', '[quietly]', '...I did not come back for the mill. I came back for you.'),
 ('S3', '[softly]', 'I know, son. I know.'),
])
scene('dispute', 'tense', [('S1', 'f', 'merchant'), ('S2', 'm', 'tax collector')], [
 ('S2', '', 'Your stall pays the market tax. Five silver.'),
 ('S1', '', 'I paid last week.'),
 ('S2', '', 'This is this week.'),
 ('S1', '[annoyed]', 'The tax is every month, not every week. Everyone knows that.'),
 ('S2', '', 'The lord changed it.'),
 ('S1', '[skeptical]', 'Then show me the paper with his seal.'),
 ('S2', '', 'I do not have the paper here.'),
 ('S1', '', 'Then come back with the paper, and I pay. Not before.'),
])
scene('dispute', 'heated', [('S1', 'm', 'soldier'), ('S2', 'm', 'soldier'), ('S3', 'm', 'sergeant'), ('S4', 'f', 'cook')], [
 ('S1', '', 'That was my bread. I put it on the barrel.'),
 ('S2', '', 'There was no name on it.'),
 ('S1', '[angry]', 'It does not need a name! It was on MY barrel!'),
 ('S4', '[annoyed]', 'There is more bread. Stop shouting in my kitchen.'),
 ('S2', '', 'See? More bread. Go get some.'),
 ('S1', '[angry]', 'I do not want more bread, I want MY bread!'),
 ('S3', '[shouts]', 'Quiet! Both of you, outside. Now.'),
 ('S4', '[chuckles]', 'Every night the same war. Over bread.'),
])

# ---------------- small talk ----------------
scene('small_talk', 'calm', [('S1', 'f', 'villager'), ('S2', 'f', 'villager')], [
 ('S1', '', 'Morning. The wind is cold today.'),
 ('S2', '', 'It came from the mountains last night. My door was shaking.'),
 ('S1', '', 'Snow before the end of the month, I think.'),
 ('S2', '', 'My knee says the same. It always knows.'),
 ('S1', '[chuckles]', 'Better than any priest.'),
 ('S2', '', 'Are you going to the market?'),
 ('S1', '', 'Later. I need wool, and maybe some onions.'),
 ('S2', '', 'Ask for Berta. She has the good onions this year.'),
])
scene('small_talk', 'calm', [('S1', 'm', 'guard'), ('S2', 'm', 'guard')], [
 ('S1', '', 'Quiet night.'),
 ('S2', '', 'Too quiet. I like a little noise. A dog, a drunk, something.'),
 ('S1', '', 'You want a drunk? Wait until the tavern closes.'),
 ('S2', '[chuckles]', 'True. How is your wife?'),
 ('S1', '', 'Tired. The baby does not sleep. So nobody sleeps.'),
 ('S2', '', 'Mine was the same. It gets better after the first teeth.'),
 ('S1', '[sighs]', 'I hope so. I fell asleep standing yesterday.'),
 ('S2', '', 'Standing? That is a soldier.'),
])
scene('small_talk', 'warm', [('S1', 'f', 'mother'), ('S2', 'm', 'father'), ('S3', 'f', 'daughter')], [
 ('S1', '', 'Wash your hands before you touch the bread.'),
 ('S3', '', 'They are clean.'),
 ('S2', '[amused]', 'They are the colour of the garden.'),
 ('S3', '', 'It is good dirt.'),
 ('S1', '', 'Good dirt goes in the garden, not on the table.'),
 ('S2', '', 'How was the river today?'),
 ('S3', '[excited]', 'I saw a fish as long as my arm!'),
 ('S2', '[chuckles]', 'As long as your arm, or as long as my arm?'),
 ('S3', '', 'As long as your arm. Almost.'),
])
scene('small_talk', 'calm', [('S1', 'm', 'traveller'), ('S2', 'm', 'traveller'), ('S3', 'f', 'traveller')], [
 ('S1', '', 'How far to the next village?'),
 ('S3', '', 'Half a day if the road is dry.'),
 ('S2', '', 'It is never dry.'),
 ('S3', '', 'Then a full day.'),
 ('S1', '', 'Do they have an inn?'),
 ('S3', '', 'They have a barn and a woman who makes very good soup.'),
 ('S2', '', 'That is better than most inns.'),
 ('S1', '[warmly]', 'Then we walk for the soup.'),
])
scene('small_talk', 'calm', [('S1', 'm', 'fisherman'), ('S2', 'm', 'fisherman'), ('S3', 'm', 'boy'), ('S4', 'f', 'fishwife')], [
 ('S1', '', 'Nets are full of weed again.'),
 ('S2', '', 'The storm pushed it in. Two more days, it goes out again.'),
 ('S3', '', 'Can I come on the boat tomorrow?'),
 ('S1', '', 'If your mother says yes.'),
 ('S4', '', 'His mother says he can clean the fish today, then we see.'),
 ('S3', '[sighs]', 'Every day the fish.'),
 ('S2', '[chuckles]', 'Every day the fish for all of us, boy. Welcome to the sea.'),
 ('S4', '', 'And tell your father his supper is getting cold.'),
])

# ---------------- banter ----------------
scene('banter', 'playful', [('S1', 'm', 'soldier'), ('S2', 'f', 'soldier'), ('S3', 'm', 'soldier')], [
 ('S1', '', 'I bet you a coin I can hit the crow on that post.'),
 ('S2', '[amused]', 'You cannot hit the post.'),
 ('S3', '', 'He hit a post once. By accident.'),
 ('S1', '', 'Watch and learn.'),
 ('S2', '', '...'),
 ('S3', '[laughs]', 'The crow is laughing at you.'),
 ('S2', '', 'Pay up.'),
 ('S1', '[sighs]', 'The wind moved it. The wind.'),
])
scene('banter', 'playful', [('S1', 'f', 'cook'), ('S2', 'm', 'stable boy')], [
 ('S2', '', 'What is in the pot today?'),
 ('S1', '', 'Soup.'),
 ('S2', '', 'What kind of soup?'),
 ('S1', '[amused]', 'The kind that is hot and wet. Do you want it or not?'),
 ('S2', '', 'Yesterday it was also hot and wet, and it tasted like boots.'),
 ('S1', '', 'Yesterday you cleaned the boots in my water bucket.'),
 ('S2', '[nervous]', '...Ah. I will eat the soup.'),
])

# ---------------- emotional ----------------
scene('emotional', 'grief', [('S1', 'f', 'widow'), ('S2', 'f', 'neighbour')], [
 ('S2', '[softly]', 'I brought some bread. And a little honey.'),
 ('S1', '', 'You did not have to.'),
 ('S2', '', 'I know. Have you eaten today?'),
 ('S1', '[sad]', 'I made two bowls this morning. Out of habit. Two bowls.'),
 ('S2', '[softly]', 'Then I will eat the other one with you.'),
 ('S1', '', 'He always burned his tongue. Every morning. He never waited.'),
 ('S2', '[warmly]', 'He never waited for anything. That was him.'),
])
scene('emotional', 'fear', [('S1', 'f', 'healer'), ('S2', 'm', 'wounded soldier'), ('S3', 'm', 'soldier')], [
 ('S2', '[panicked]', 'I cannot feel my hand. I cannot feel my hand!'),
 ('S1', '[firmly]', 'Look at me. Look at me. Breathe.'),
 ('S3', '[worried]', 'Is it bad?'),
 ('S1', '', 'It is deep, but it is clean. Hold this. Press hard.'),
 ('S2', '[nervous]', 'Am I going to lose it?'),
 ('S1', '[calmly]', 'Not today. Today you lose a little blood and a lot of pride.'),
 ('S2', '', '...That is not funny.'),
 ('S3', '[chuckles]', 'It is a little funny.'),
])
scene('emotional', 'joy', [('S1', 'm', 'father'), ('S2', 'f', 'midwife'), ('S3', 'f', 'grandmother')], [
 ('S2', '[warmly]', 'A girl. Healthy and loud.'),
 ('S1', '[excited]', 'A girl! Can I see her?'),
 ('S2', '', 'Wash your hands first. You smell like a horse.'),
 ('S3', '[laughs]', 'He always smells like a horse.'),
 ('S1', '[softly]', 'She is so small. Look at her hands.'),
 ('S3', '[warmly]', 'She has your mother\'s nose. Poor thing.'),
 ('S1', '[laughs]', 'Mother!'),
])

ORIGINALS = S
if __name__ == '__main__':
    import collections
    print(len(S), collections.Counter(s['category'] for s in S), collections.Counter(len(s['speakers']) for s in S))
