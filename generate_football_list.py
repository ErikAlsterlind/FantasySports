# Script for generating a CSV list of players for fantasy football
from bs4 import BeautifulSoup
from bs4 import SoupStrainer
import csv
import time
import numpy as np
import os
import requests
import re
import struct
import sys
import time
import unidecode

# Useful globals, curr_year determines which year's stats are pulled
# and total_players caps the player list to something useful for a 15 round draft.
curr_year = 2020
total_players = 500
pos_dict = {'RB':1, 'WR':1, 'TE':1, 'QB':1, 'K':1, 'DEF':1}
rb_stat_labels = ["rush_att", "rush_yds","rec", "rec_yds", "rush_td"]
wr_stat_labels = ["rec", "rec_yds", "rec_td"]
qb_stat_labels = ["pass_cmp", "pass_yds", "pass_td", "pass_int"]
player_list = []
sorted_player_dict = {'RB':[], 'WR':[], 'TE':[], 'QB':[], 'K':[], 'DEF':[]}

# Generic class to define a player when parsing and storing stats
class Player:
  def __init__ (self):
    self.name = ""
    self.team = ""
    self.position = ""
    self.avg_pick = 0.0
    self.avg_round = 0.0
    self.pos_count = ""
    self.pfr_stats = None
    self.pfr_ranks = None
    self.points = [0.0, 0.0]

  def set_name(self, name):
    self.name = name
  def set_team(self, team):
    self.team = team.upper()
  def set_pick(self, pick):
    self.avg_pick = pick
  def set_round(self, avg_round):
    self.avg_round = avg_round
  def set_pos(self, pos):
    self.position = pos
    self.pos_count = pos + str(pos_dict[pos])
    pos_dict[pos] += 1
  def set_pfr_stats(self, stats):
    self.pfr_stats = stats
  def set_pfr_ranks(self, ranks):
    self.pfr_ranks = ranks
  def set_points(self, points):
    self.points = points

  def get_pos(self):
    return self.position
  def get_name(self):
    return self.name
  def get_pfr_stats(self):
    return self.pfr_stats
  def get_pfr_ranks(self):
    return self.pfr_ranks
  def get_points(self):
    return self.points

  def print_all(self):
    print("name: %s, avg pick: %.02f, avg round: %.02f, position: %s, pos count: %s" % (self.name, self.avg_pick, self.avg_round, self.position, self.pos_count))

# Defenses are treated as a special case so they have been given their own class
# instead of a child class of player.
class Defense:
  def __init__ (self):
    self.name = ""
    self.team = ""
    self.avg_pick = 0.0
    self.avg_round = 0.0
    self.pos_count = ""
    self.total_dvoa = None
    self.run_dvoa = None
    self.pass_dvoa = None

  def set_name(self, name):
    self.name = name
  def set_team(self, team):
    self.team = team.upper()
  def set_pick(self, pick):
    self.avg_pick = pick
  def set_round(self, avg_round):
    self.avg_round = avg_round
  def set_pos(self, pos):
    self.pos_count = pos + str(pos_dict[pos])
    pos_dict[pos] += 1
  def set_dvoa(self, ranks):
    self.total_dvoa = ranks[0]
    self.pass_dvoa = ranks[1]
    self.run_dvoa = ranks[2]

  def get_pos(self):
    return "DEF"
  def get_team(self):
    return self.team
  def get_name(self):
    return self.name
  def get_dvoa(self):
    return [self.total_dvoa, self.pass_dvoa, self.run_dvoa]

  def print_all(self):
    print("name: %s, avg pick: %.02f, avg round: %.02f, position: %s, pos count: %s" % (self.name, self.avg_pick, self.avg_round, self.position, self.pos_count))


# Function that scrapes the players and their draft stats from the Yahoo Draft Analysis Page.
# The webscraping here is entirely dependent on the 'table' element in the webpage that 
# hasn't really changed, which allows this function to stay pretty stable.
def Add_Yahoo_Stats():
  print "Adding Players from Yahoo"
  player_count = 0
  new_page = "https://football.fantasysports.yahoo.com/f1/draftanalysis"
  table_strainer=SoupStrainer("table", id="draftanalysistable")
  while (player_count < total_players) and not (player_count % 50):
    page = requests.get(new_page)
    soup = BeautifulSoup(page.text, parse_only=table_strainer)
    body = soup.tbody

    for player in body.contents:
      pos_raw = player.find("span", class_="Fz-xxs")
      pos_strip = u''.join((pos_raw.text)).encode('utf-8').strip()
      team = re.search("(.+?) -", pos_strip).group(1)
      pos_strip = re.search("- (.+$)", pos_strip).group(1)
      if pos_strip == "DEF":
        temp = Defense()
        player_list.append(temp)
      else:
        temp = Player()
        player_list.append(temp)
      player_list[player_count].set_team(team)
      player_list[player_count].set_pos(pos_strip)

      name = player.find("a", class_="Nowrap name F-link")
      name_strip = u''.join((name.text)).encode('utf-8').strip()
      name_clean = unidecode.unidecode(name_strip.decode('utf-8'))
      player_list[player_count].set_name(name_clean)

      find_pick = player.find("td", class_="Ta-end")
      pick_strip = u''.join((find_pick.div.text)).encode('utf-8').strip()
      player_list[player_count].set_pick(float(pick_strip))

      find_round = player.find("td", class_="Alt Last")
      round_strip = u''.join((find_round.div.text)).encode('utf-8').strip()
      player_list[player_count].set_round(float(round_strip))
    
      sorted_player_dict[pos_strip].append(player_list[player_count])
      player_count += 1
      if player_count == total_players:
        break

    # An ad hoc way to get the next page of players in the table
    new_page = "https://football.fantasysports.yahoo.com/f1/draftanalysis?tab=SD&pos=ALL&sort=DA_AP&count={}".format(player_count)

# This function is used to extract a specific player's PFR page ID from a general table of all players.
# The table is searched for the target player using a specific element in each entry that is regular 
# (ie omits things like "III" or "Jr" which aren't always consistent with Yahoo) and extracts the page
# identifier from the same element.
def Find_PFR_Entry(soup, target_name):
  split_name = target_name.split(" ")
  target_name = split_name[1] + "," + split_name[0]
  pfr = soup.find_all('td', csk=target_name)
  if len(pfr) == 1:
    return pfr[0].find_all("a")
  else:
    if len(split_name[0]) == 2 and split_name[0].isupper():
      split_name[0] = split_name[0][0] + "." +  split_name[0][1] + "."
      target_name = split_name[1] + "," + split_name[0]
      pfr = soup.find_all('td', csk=target_name)
      if len(pfr) == 1:
        return pfr[0].find_all("a")
    return None

# Function that scrapes RB stats a pro football reference based on the rushing stats page.
def Add_RB_PFR_Stats():
  print "Adding RB PFR Data"
  rb_page = "https://www.pro-football-reference.com/years/"+ str(curr_year-1) + "/rushing.htm"
  table_strainer=SoupStrainer("table", id="rushing")
  rb_page = requests.get(rb_page)
  rb_soup = BeautifulSoup(rb_page.text, parse_only=table_strainer)

  for player in sorted_player_dict["RB"]:
    name = player.get_name()
    print name
    if re.search(" (.+?) ", name) != None:
      name = re.search("(.+?) ", name).group(1) + " " + re.search(" (.+?) ", name).group(1)
    pfr = Find_PFR_Entry(rb_soup, name)

    rb_data_dict = {}
    rb_rank_dict = {}
    if pfr and len(pfr) == 1:
      pfr_page = "https://www.pro-football-reference.com" + str(pfr[0].attrs.get("href") + "/gamelog/" + str(curr_year - 1) + "/")
      game_strainer = SoupStrainer("table", id="stats")
      game_page = requests.get(pfr_page)
      game_soup = BeautifulSoup(game_page.text, parse_only=game_strainer)
      game_body = game_soup.tbody
      for label in rb_stat_labels:
        arr = []
        rb_data_dict[label] = game_body.find_all("td", {"data-stat": label})
        if len(rb_data_dict[label]) > 0:
          for week in rb_data_dict[label]:
            if week.text.isnumeric():
              arr.append(float(week.text))
            else:
              arr.append(0.0)
        else:
          arr = [0.0]
        rb_data_dict[label] = [round(np.mean(arr), 2), round(np.std(arr), 2)]
        rb_rank_dict[label] = [1, 1]
    else:
      for label in rb_stat_labels:
        rb_data_dict[label] = [0, 0]
        rb_rank_dict[label] = [0, 0]
    player.set_pfr_stats(rb_data_dict)          
    player.set_pfr_ranks(rb_rank_dict)          

  print " Adding pfr ranks"
  for spot, player in enumerate(sorted_player_dict["RB"]):
    ranks = player.get_pfr_ranks()
    data = player.get_pfr_stats()
    if data[rb_stat_labels[0]][0] == 0:
      print "   " + player.get_name() + " is a rookie"
      continue
    for ind in range(0, pos_dict["RB"] - 1):
      for label in rb_stat_labels:
        comp_stats = sorted_player_dict["RB"][ind].get_pfr_stats()
        if (ind == spot) or (comp_stats[label][0] == 0):
          continue

        if data[label][0] < comp_stats[label][0]:
          ranks[label][0] += 1
        if data[label][1] > comp_stats[label][1]:
          ranks[label][1] += 1
    player.set_pfr_ranks(ranks)

  # Here three "stats" are calculated:
  #   - Average points: (avg rush yard * 0.1) + (avg rec yards * 0.1) + (avg rec * 0.5) + (avg rush tds * 6)
  #   - "Expected" points: Average points without the TDs to give a better idea of a general floor
  #   - Point volatility: crude approximation of point volatility using standard deviation of each stat.
  # Score values are based on our league rules, like 6 points for a rushing TD.
  # Receiving yards are excluded because, in my opinion, they don't represent an important enough
  # component of RB points week to week to be a difference maker when evaluating different players.
  print " Calulating expected points"
  num_dev = 1
  for player in sorted_player_dict["RB"]:
    stats = player.get_pfr_stats()
    rush_yds = stats["rush_yds"]
    rec = stats["rec"]
    rec_yds = stats["rec_yds"]
    rush_td = stats["rush_td"]
    bad = 0.0
    avg = 0.0
    good = 0.0
    bad += ((rush_yds[0] - (rush_yds[1] * num_dev)) * 0.1)            
    avg += (rush_yds[0] * 0.1)
    good += ((rush_yds[0] + (rush_yds[1] * num_dev)) * 0.1)
    bad += ((rec[0] + (rec[1] * num_dev)) * 0.5)    
    avg += (rec[0] * 0.5)
    good += ((rec[0] - (rec[1] * num_dev)) * 0.5)
    bad += ((rec_yds[0] + (rec_yds[1] * num_dev)) * 0.1)            
    avg += (rec_yds[0] * 0.1)
    good += ((rec_yds[0] - (rec_yds[1] * num_dev)) * 0.1)            
    avg_with_td = avg + (rush_td[0] * 6)
    player.set_points([avg_with_td, avg, abs(bad - good)])            

# Function that scrapes WR or TE stats a pro football reference based on the receiving stats page.
def Add_Rec_PFR_Stats(receiver_type):
  print "Adding " + receiver_type + " PFR Data"
  wr_page = "https://www.pro-football-reference.com/years/" + str(curr_year-1) + "/receiving.htm"
  table_strainer=SoupStrainer("table", id="receiving")
  wr_page = requests.get(wr_page)
  wr_soup = BeautifulSoup(wr_page.text, parse_only=table_strainer)

  for player in sorted_player_dict[receiver_type]:
    name = player.get_name()
    print name
    if re.search(" (.+?) ", name) != None:
      name = re.search("(.+?) ", name).group(1) + " " + re.search(" (.+?) ", name).group(1)
    pfr = Find_PFR_Entry(wr_soup, name)

    wr_data_dict = {}
    if pfr and len(pfr) == 1:
      pfr_page = "https://www.pro-football-reference.com" + str(pfr[0].attrs.get("href") + "/gamelog/" + str(curr_year - 1) + "/")
      game_strainer = SoupStrainer("table", id="stats")
      game_page = requests.get(pfr_page)
      game_soup = BeautifulSoup(game_page.text, parse_only=game_strainer)
      game_body = game_soup.tbody
      for label in wr_stat_labels:
        arr = []
        wr_data_dict[label] = game_body.find_all("td", {"data-stat": label})
        for week in wr_data_dict[label]:
          if week.text.isnumeric():
            arr.append(float(week.text))
          else:
            arr.append(0.0)
        wr_data_dict[label] = [round(np.mean(arr), 2), round(np.std(arr), 2)]
    else:
      for label in wr_stat_labels:
        wr_data_dict[label] = [0, 0]
    player.set_pfr_stats(wr_data_dict)

  # Here three "stats" are calculated:
  #   - Average points: (avg rec yards * 0.1) + (avg rec * 0.5) + (avg rec tds * 5)
  #   - "Expected" points: Average points without the TDs to give a better idea of a general floor
  #   - Point volatility: crude approximation of point volatility using standard deviation of each stat.
  # Score values are based on our league rules, like 5 points for a receiving TD. 
  print " Calulating expected points"
  num_dev = 1
  for player in sorted_player_dict[receiver_type]:
    stats = player.get_pfr_stats()
    rec_yds = stats["rec_yds"]
    rec = stats["rec"]
    rec_td = stats["rec_td"]
    bad = 0.0
    avg = 0.0
    good = 0.0
    bad += ((rec[0] - (rec[1] * num_dev)) * 0.5)    
    avg += (rec[0] * 0.5)
    good += ((rec[0] + (rec[1] * num_dev)) * 0.5)
    bad += ((rec_yds[0] - (rec_yds[1] * num_dev)) * 0.1)            
    avg += (rec_yds[0] * 0.1)
    good += ((rec_yds[0] + (rec_yds[1] * num_dev)) * 0.1)            
    avg_with_td = avg + (rec_td[0] * 5)
    player.set_points([avg_with_td, avg, abs(bad - good)])            

# Function that scrapes QB stats a pro football reference based on the passing stats page.
def Add_QB_PFR_Stats():
  print "Adding QB PFR Data"
  qb_page = "https://www.pro-football-reference.com/years/" + str(curr_year-1) + "/passing.htm"
  table_strainer=SoupStrainer("table", id="passing")
  qb_page = requests.get(qb_page)
  qb_soup = BeautifulSoup(qb_page.text, parse_only=table_strainer)

  for player in sorted_player_dict["QB"]:
    name = player.get_name()
    print name
    if re.search(" (.+?) ", name) != None:
      name = re.search("(.+?) ", name).group(1) + " " + re.search(" (.+?) ", name).group(1)
    pfr = Find_PFR_Entry(qb_soup, name)
 
    qb_data_dict = {}
    if pfr and len(pfr) == 1:
      pfr_page = "https://www.pro-football-reference.com" + str(pfr[0].attrs.get("href") + "/gamelog/" + str(curr_year - 1) + "/")
      game_strainer = SoupStrainer("table", id="stats")
      game_page = requests.get(pfr_page)
      game_soup = BeautifulSoup(game_page.text, parse_only=game_strainer)
      game_body = game_soup.tbody
      for label in qb_stat_labels:
        arr = []
        qb_data_dict[label] = game_body.find_all("td", {"data-stat": label})
        for week in qb_data_dict[label]:
          if week.text.isnumeric():
            arr.append(float(week.text))
          else:
            arr.append(0.0)
        qb_data_dict[label] = [round(np.mean(arr), 2), round(np.std(arr), 2)]
    else:
      for label in qb_stat_labels:
        qb_data_dict[label] = [0, 0]
    player.set_pfr_stats(qb_data_dict)

  # Here three "stats" are calculated:
  #   - Average points: (avg pass completions * 0.25) + (avg pass yards * 0.04) + (avg pass tds * 4) - (avg ints * 2)
  #   - "Expected" points: Average points without the TDs to give a better idea of a general floor
  #   - Point volatility: crude approximation of point volatility using standard deviation of each stat.
  # Score values are based on our league rules, like 4 points for a passing TD. 
  # The total avg points aren't currently passed along as they are so volatile for QBs generally.
  # Overall volatility is also very high for QBs relative to other positions, almost to the point of being useless.
  print " Calulating expected points"
  num_dev = 1
  for player in sorted_player_dict["QB"]:
    stats = player.get_pfr_stats()
    pass_yds = stats["pass_yds"]
    pass_cmp = stats["pass_cmp"]
    pass_td = stats["pass_td"]
    ints = stats["pass_int"]
    bad = 0.0
    avg = 0.0
    good = 0.0
    bad += ((pass_cmp[0] - (pass_cmp[1] * num_dev)) * 0.25)   
    avg += (pass_cmp[0] * 0.25)
    good += ((pass_cmp[0] + (pass_cmp[1] * num_dev)) * 0.25)
    bad += ((pass_yds[0] - (pass_yds[1] * num_dev)) * 0.04)           
    avg += (pass_yds[0] * 0.04)
    good += ((pass_yds[0] + (pass_yds[1] * num_dev)) * 0.04)             
    bad += ((pass_td[0] - (pass_td[1] * num_dev)) * 4.0)            
    avg += (pass_td[0] * 4.0)
    good += ((pass_td[0] + (pass_td[1] * num_dev)) * 4.0)            
    bad += ((ints[0] + (ints[1] * num_dev)) * -2.0)            
    avg += (ints[0] * -2.0)
    good += ((ints[0] + (ints[1] * num_dev)) * -2.0)            

    player.set_points([avg, abs(bad - good)])            

# Function that scrapes DEF DVOA stats from football outsiders
def Add_DEF_DVOA():
  print "Adding DEF DVOA Data"
  ovr_rank = 0
  pass_rank = 7
  run_rank = 9
  def_page = "https://www.footballoutsiders.com/stats/nfl/team-defense/" + str(curr_year - 1) 
  table_strainer = SoupStrainer("table", {"class":"sticky-headers sortable stats"})
  def_page = requests.get(def_page)
  def_soup = BeautifulSoup(def_page.text, parse_only=table_strainer)
  defenses = []
  trs = def_soup.find_all("tr")
  for tr in trs:
    th = tr.find("td")
    if th != None:
      defenses.append(tr)
  for player in sorted_player_dict["DEF"]:
    for defense in defenses:
      def_stats = defense.find_all("td")
      if def_stats[1].text == player.get_team():
        player.set_dvoa([def_stats[ovr_rank].text, def_stats[pass_rank].text, def_stats[run_rank].text])

# Function that writes player list with stats to a CSV file in local directory.
# The "sort_type" parameter determines if players are listed by position or if its a raw list of all positions.
def Write_CSV(sort_type):
  global player_list
  print "Starting CSV Write"
  headers = ["Name", "Team", "Avg Pick", "Avg Round", "Pos Rank"]
  curr_dir = os.getcwd()
  curr_time = time.time()
  base_name = "football_raw_list_" if sort_type == 0 else "football_positional_analysis_"
  player_file = curr_dir + "/" + base_name + "{}_".format(curr_year) + str(int(curr_time)) + ".csv"
  csvfile = open(player_file, "wb")
  file_writer = csv.writer(csvfile, delimiter=',')
  file_writer.writerow(headers)
  pos_order = ["RB", "WR", "TE", "QB", "K", "DEF"]

  if sort_type == 0:
    for player in player_list:
      player_list = []
      player_list.append(player.name)
      player_list.append(player.team)
      player_list.append(player.avg_pick)
      player_list.append(player.avg_round)
      player_list.append(player.pos_count)
      file_writer.writerow(player_list)

  elif sort_type == 1:
    for pos in pos_order:
      print pos
      sub_header = [pos] + ["" for x in range(len(headers)-1)]
      if pos == "RB":
        for label in rb_stat_labels:
          sub_header.append(label + " avg")
      elif pos == "WR" or pos == "TE":
        for label in wr_stat_labels:
          sub_header.append(label + " avg")
      elif pos == "QB":
        for label in qb_stat_labels:
          sub_header.append(label + " avg")
      if pos != "QB" and pos != "DEF":
        sub_header.append("Avg Total Points")
      if pos != "DEF":
        sub_header.append("Avg Exp Points")
        sub_header.append("Point Volatility")
      else:
        sub_header.append("Overall DVOA Rank")
        sub_header.append("Pass DVOA Rank")
        sub_header.append("Run DVOA Rank")
      file_writer.writerow(sub_header)

      for player in sorted_player_dict[pos]:
        player_write = []
        player_write.append(player.name)
        player_write.append(player.team)
        player_write.append(player.avg_pick)
        player_write.append(player.avg_round)
        player_write.append(player.pos_count)
        if player.get_pos() == "DEF":
          stats = player.get_dvoa()
          player_write.append(stats[0])
          player_write.append(stats[1])
          player_write.append(stats[2])
        else:
          stat_dict = player.get_pfr_stats()
          points = player.get_points()
          if pos == "RB":
            for label in rb_stat_labels:
              stat = stat_dict[label]
              player_write.append(str(stat[0]))
          elif pos == "WR" or pos == "TE":
            for label in wr_stat_labels:
              stat = stat_dict[label]
              player_write.append(str(stat[0]))
          elif pos == "QB":
            for label in qb_stat_labels:
              stat = stat_dict[label]
              player_write.append(str(stat[0]))
          for point in points:
            player_write.append(point)

        file_writer.writerow(player_write)
      file_writer.writerow([])

  csvfile.close()
  print "File {} written.".format(player_file)

# Function for if incorrect or "help" parameter is passed to the script
def Print_Help():
  print "Permitted arguments for this script:"
  print "   > no arguments: generate unsorted list of players with stats"
  print "   > \"sorted\": generate list of players sorted and separated by position"
  print "   > \"-h\": print this help message"

# Main function that does a small argument check for a small set of options
def main():
  sort_type = 0
  if len(sys.argv) != 1:
    if sys.argv[1] == "-h":
      Print_Help()
      return
    elif sys.argv[1] == "sorted":
      sort_type = 1
    else:
      print "Invalid input."
      Print_Help()
      return

  Add_Yahoo_Stats()
  Add_RB_PFR_Stats()
  Add_Rec_PFR_Stats("WR")
  Add_Rec_PFR_Stats("TE")
  Add_QB_PFR_Stats()
  Add_DEF_DVOA()
  Write_CSV(sort_type)

# Entry point of script
if __name__ == "__main__":
  main()
