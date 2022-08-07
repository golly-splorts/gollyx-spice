from .instrumented_simulators import (
    HellmouthGOL_Instrumented,
    PseudoGOL_Instrumented,
    ToroidalGOL_Instrumented,
    #DragonGOL_Instrumented,
    #RainbowGOL_Instrumented,
    StarGOL_Instrumented,
    KleinGOL_Instrumented,
)

# Instead of HellmouthGOL, use HellmouthGOL_Instrumented

class SpiceManager(object):

    CupDataClass = CupBase

    def __init__(
        inputdir,
        outputdir,
        season0
    ):
        if not os.path.isdir(inputdir):
            raise Exception(f"Error: specified input dir {inputdir} does not exist")
        if not os.path.isdir(outputdir):
            raise Exception(f"Error: specified output dir {outputdir} does not exist")

        self.inputdir = inputdir
        self.outputdir = outputdir
        self.season0 = season0

        # have to load the season into self.season

    def simulate_game(self, game, fixed_ngenerations):
        """
        Simulate a single game. If fixed_ngeneations is 0,
        use the default stopping critera, otherwise stop the
        simulation after fixed_ngenerations generations.

        Stopping criteria is not determined here.
        Each cup has its own GOL class, and stopping
        criteria is determined/implemented by that class.
        """
        s1 = game['map']['initialConditions1']
        s2 = game['map']['initialConditions2']
        rows = game['map']["rows"]
        columns = game['map']["columns"]

        if 'id' in game.keys():
            gameid = game['id']
        elif 'gameid' in game.keys():
            gameid = game['gameid']

        print(f"Starting spice simulation of {gameid}")
        start = time.time()
        if self.cup.lower()=="hellmouth":
            rule_b = get_cup_rule_b(self.cup)
            rule_s = get_cup_rule_s(self.cup)
            gol = HellmouthGOL_Instrumented(
                monitor_dir=self.outputdir,
                gameid=gameid,
                s1=s1, s2=s2, rows=rows, columns=columns, rule_b=rule_b, rule_s=rule_s
            )
        elif self.cup.lower()=="toroidal":
            rule_b = get_cup_rule_b(self.cup)
            rule_s = get_cup_rule_s(self.cup)
            gol = ToroidalGOL_Instrumented(
                monitor_dir=self.outputdir,
                gameid=gameid,
                s1=s1, s2=s2, rows=rows, columns=columns, rule_b=rule_b, rule_s=rule_s
            )
        elif self.cup.lower()=="pseudo":
            rule_b = get_cup_rule_b(self.cup)
            rule_s = get_cup_rule_s(self.cup)
            gol = PseudoGOL_Instrumented(
                monitor_dir=self.outputdir,
                gameid=gameid,
                s1=s1, s2=s2, rows=rows, columns=columns, rule_b=rule_b, rule_s=rule_s
            )
        # Rainbow?
        # Dragon?
        elif self.cup.lower()=="star":
            rule_b = get_cup_rule_b(self.cup)
            rule_s = get_cup_rule_s(self.cup)
            rule_c = get_cup_rule_c(self.cup)
            gol = StarGOLGenerations_Instrumented(
                monitor_dir=self.outputdir,
                gameid=gameid,
                s1=s1, s2=s2, rows=rows, columns=columns, rule_b=rule_b, rule_s=rule_s, rule_c=rule_c
            )
        elif self.cup.lower()=="klein":
            rule_b = get_cup_rule_b(self.cup)
            rule_s = get_cup_rule_s(self.cup)
            gol = KleinGOL_Instrumented(
                monitor_dir=self.outputdir,
                gameid=gameid,
                s1=s1, s2=s2, rows=rows, columns=columns, rule_b=rule_b, rule_s=rule_s
            )
        else:
            raise ValueError(f"Unrecognized cup: {self.cup}")

        while (fixed_ngenerations == 0 and gol.running) or (
            fixed_ngenerations > 0 and gol.generation < fixed_ngenerations
        ):
            gol.next_step()

        # Extract the information to be exported...


        # Output game to tmpdir/<game-id>.json
        gamejson = os.path.join(self.tmpdir, game["id"] + ".json")
        with open(gamejson, "w") as f:
            json.dump(game, f, indent=4)

        time.sleep(1)
        print(f"{prefix}Wrote game data to {gamejson}")


    def season_map(self, threadpoolsize=2):
        """
        Perform the map step of the season generation map-reduce.

        Games are generated by separate threads,
        which write to a file in oiutputdir (named gameid.json)
        with the outcome when they are complete.

        Start by creating a list of all game ids,
        and figure out which games have been completed.
        Create a thread queue and add the remaining games.

        If all games are complete, does nothing.
        """
        all_games = {}

        for day in self.season:
            for game in day:
                if 'id' in game.keys():
                    gameid = game['id']
                elif 'gameid' in game.keys():
                    gameid = game['gameid']
                all_games[gameid] = game
        all_gameids = set(all_games.keys())

        # Get the list of all <uuid>.json files and strip the extension 
        # to get the list of game uuids that have already been simulated
        completed_gameids = {
            os.path.splitext(os.path.basename(j))[0]
            for j in glob.glob(f"{self.outputdir}/*")
        }
        todo_gameids = all_gameids - completed_gameids
        todo_games = {k: v for k, v in all_games.items() if k in todo_gameids}

        self._fill_threadpool(todo_games)

    def postseason_map(self, threadpoolsize=2):
        """
        Perform the map step of the postseason generation map-reduce.
        """
        all_games = {}

        for series in self.post:
            miniseason = self.post[series]
            for day in miniseason:
                for game in day:
                    if 'id' in game.keys():
                        gameid = game['id']
                    elif 'gameid' in game.keys():
                        gameid = game['gameid']
                    all_games[gameid] = game
        all_gameids = set(all_games.keys())

        # Get the list of all <uuid>.json files and strip the extension 
        # to get the list of game uuids that have already been simulated
        completed_gameids = {
            os.path.splitext(os.path.basename(j))[0]
            for j in glob.glob(f"{self.outputdir}/*")
        }
        todo_gameids = all_gameids - completed_gameids
        todo_games = {k: v for k, v in all_games.items() if k in todo_gameids}

        self._fill_threadpool(todo_games)

    def _fill_threadpool(self, todo_games):

        if self.test_mode == "":
            # Real mode
            # Each thread will take game data as input, and dump out a json file
            pool = ThreadPool(threadpoolsize)
            threadholder = []
            for gameid, game in todo_games.items():
                print(
                    f"    Processing game {gameid} (season0={game['season']} day0={game['day']} fixed_ngenerations={self.backend.fixed_ngenerations})"
                )
                args = [game, self.backend.fixed_ngenerations]
                threadholder.append(
                    pool.apply_async(self.simulate_game, args=args)
                )
            # Wait until pool is completely empty
            print("    Waiting for thread pool to close...")
            [t.wait() for t in threadholder]
            pool.close()
            pool.join()
            print("    Thread pool has been closed.")
            print(" *** Congratulations, the season is finished! *** ")

        elif self.test_mode == "fake":
            for gameid, game in todo_games.items():
                print(
                    f"    Processing game {gameid} (season0={game['season']} day0={game['day']} fixed_ngenerations={self.backend.fixed_ngenerations})"
                )
                self.fake_simulate_sensitive_game(game, self.backend.fixed_ngenerations)

        elif self.test_mode == "real":
            for gameid, game in todo_games.items():
                print(
                    f"    Processing game {gameid} (season0={game['season']} day0={game['day']} fixed_ngenerations={self.backend.fixed_ngenerations})"
                )
                # kludge to prevent stuck in infinite loop
                game['patternName'] = 'random'
                self.simulate_sensitive_game(game, self.backend.fixed_ngenerations)

        else:
            raise Exception(f"Error: could not determine mode from {self.test_mode}")

    def season_reduce(self, write=True):
        """
        Perform the reduce step of the season generation map-reduce.

        Determine whether all games in the schedule have been completed.
        If so, compute win/loss records, clean up games, and combined them
        into a single season.json file to be output.
        """
        pass

    def postseason_reduce(self, write=True):
        """
        Perform the reduce step of the postseason generation map-reduce.
        """
        pass

class HellmouthSpiceManager(SpiceManager):
    CupDataClass = HellmouthCup

class PseudoSpiceManager(SpiceManager):
    CupDataClass = PseudoCup

class ToroidalSpiceManager(SpiceManager):
    CupDataClass = ToroidalCup

#class DragonSpiceManager(SpiceManager):
#    CupDataClass = DragonCup

#class RainbowSpiceManager(SpiceManager):
#    CupDataClass = RainbowCup

class StarSpiceManager(SpiceManager):
    CupDataClass = StarCup

class KleinSpiceManager(SpiceManager):
    CupDataClass = KleinCup
