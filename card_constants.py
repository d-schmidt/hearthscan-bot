
setdata = {
    '01' : {'name' : 'Basic', 'n' : False, 'g' : False, 'std' : True},
    '02' : {'name' : 'Classic', 'n' : True, 'g' : True, 'booster' : True, 'std' : True},
    '03' : {'name' : 'Reward', 'n' : True, 'g' : True, 'std' : False},
    '04' : {'name' : 'Promo', 'n' : True, 'g' : False, 'std' : False},
    '05' : {'name' : 'Curse of Naxxramas', 'code' : 'Naxx',  'n' : True, 'g' : True, 'std' : False},
    '06' : {'name' : 'Goblin vs Gnomes', 'code' : 'GvG',  'n' : True, 'g' : True, 'booster' : True, 'std' : False},
    '07' : {'name' : 'Blackrock Mountain', 'code' : 'BRM',  'n' : False, 'g' : True, 'std' : True},
    '08' : {'name' : 'The Grand Tournament', 'code' : 'TGT', 'n' : True, 'g' : True, 'booster' : True, 'std' : True},
    '09' : {'name' : 'The League of Explorers', 'code' : 'LoE', 'n' : True, 'g' : True, 'std' : True},
    '10' : {'name' : 'Whispers of the Old Gods', 'code' : 'OG', 'n' : True, 'g' : True, 'booster' : True, 'std' : True},
    '11' : {'name' : 'One Night in Karazhan', 'code' : 'Kara', 'n' : True, 'g' : True, 'std' : True},
    '12' : {'name' : 'Mean Streets of Gadgetzan', 'code' : 'MSoG', 'n' : True, 'g' : True, 'booster' : True, 'std' : True}
}

setids = {}
for id, set in setdata.items(): setids[set['name']] = id

setorder = ['02','06','08','01','03','04','05','07','09','10','11','12']

devalue = {
    'Basic' : {'n' : 0, 'g' : 0},
    'Common' : {'n' : 5, 'g' : 50},
    'Rare' : {'n' : 20, 'g' : 100},
    'Epic' : {'n' : 100, 'g' : 400},
    'Legendary' : {'n' : 400, 'g' : 1600}
}

rarities = ['Basic','Common','Rare','Epic','Legendary']
classes = ['Druid','Hunter','Mage','Paladin','Priest','Rogue','Shaman','Warlock','Warrior','Neutral']
booster_rarity = {'Epic': 0.23, 'Rare': 1.139, 'Common': 3.572, 'Legendary': 0.0595}
booster_dust = {'Epic': 27.65, 'Rare': 28.3, 'Common': 21.1675, 'Legendary': 30.4}