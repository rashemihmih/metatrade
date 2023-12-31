import logging
import os.path
import random

LOG_FORMAT = '[%(levelname)s] %(name)s: %(message)s'
logging.basicConfig(format=LOG_FORMAT)


class Bonus:
    def __init__(self, amount):
        self.start_amount = amount
        self.amount = amount
        self.worked_amount = 0


class Account:
    def __init__(self, name):
        self.log = logging.getLogger(f'Account {name}')
        self.name = name
        self.own_balance = 0
        self.shared_own_balance = 0
        # self.total_deposit = 0
        self.total_earnings = 0
        # self.total_withdrawn = 0
        self.total_loss = 0
        self.total_bonus_loss = 0
        self.total_bonus_completed = 0
        self.bonuses = []

    def get_total_balance(self):
        return self.own_balance + self.shared_own_balance + self.get_bonus_balance()

    def get_own_balance(self):
        return self.own_balance

    def get_total_own_balance(self):
        return self.own_balance + self.shared_own_balance

    def get_bonus_balance(self):
        return sum(bonus.amount for bonus in self.bonuses)

    def get_own_rate(self):
        total_balance = self.get_total_balance()
        if total_balance == 0:
            return 1
        return self.get_total_own_balance() / self.get_total_balance()

    def deposit(self, amount, own_rate, bonuses_pieces):
        assert 0.625 <= own_rate <= 1
        assert bonuses_pieces <= 20
        own_amount = amount
        shared_own_amount = 0
        if own_rate < 1:
            remaining_bonus_pieces = 20 - len(self.bonuses)
            if bonuses_pieces > remaining_bonus_pieces:
                logging.info(f'Can\'t allocate {bonuses_pieces} bonus pieces: {len(self.bonuses)} used')
                if remaining_bonus_pieces == 0:
                    own_rate = 1
                else:
                    own_rate = bonuses_pieces / (bonuses_pieces + remaining_bonus_pieces * (1 / own_rate - 1))
                    bonuses_pieces = remaining_bonus_pieces
            bonus_amount = amount * (1 - own_rate) / own_rate
            shared_own_amount = bonus_amount / 0.6
            own_amount = amount - shared_own_amount
            bonus_piece_amount = bonus_amount / bonuses_pieces
            if bonus_amount > 0.01:
                for i in range(bonuses_pieces):
                    bonus = Bonus(bonus_piece_amount)
                    self.bonuses.append(bonus)
        self.own_balance += own_amount
        self.shared_own_balance += shared_own_amount
        self.log.debug(f'Deposit {amount}')
        # self.total_deposit += amount
        self.debug_stats()

    def withdraw(self, amount):
        assert amount > 0.01
        if not self.can_withdraw(amount):
            raise ValueError(f'Can\'t withdraw {amount}: own balance is {self.own_balance}')
        self.own_balance -= amount
        self.log.debug(f'Withdraw {amount}')
        # self.total_withdrawn += amount
        self.debug_stats()

    def can_withdraw(self, amount):
        return self.own_balance >= amount

    def earn(self, amount):
        total_balance = self.get_total_balance()
        own_share = self.get_total_own_balance() / total_balance
        bonus_balance = self.get_bonus_balance()
        bonus_share = bonus_balance / total_balance
        if len(self.bonuses) > 0:
            for bonus in self.bonuses:
                concrete_bonus_share = bonus.amount / bonus_balance * bonus_share
                bonus.amount += amount * concrete_bonus_share
        self.own_balance += amount * own_share
        self.log.debug(f'Earned {amount}')
        self.total_earnings += amount
        self.debug_stats()

    def work_bonus(self, percent):
        work_amount = percent * self.get_total_balance()
        removed_bonuses = []
        for bonus in self.bonuses:
            if work_amount <= 0:
                break
            work_left = bonus.start_amount - bonus.worked_amount
            if work_left <= work_amount:
                work_amount -= work_left
                removed_bonuses.append(bonus)
                shared_own_amount = bonus.start_amount / 0.6
                self.shared_own_balance -= shared_own_amount
                self.own_balance += bonus.amount + shared_own_amount
                self.total_bonus_completed += bonus.start_amount
            else:
                bonus.worked_amount += work_amount
                break
        for bonus in removed_bonuses:
            self.bonuses.remove(bonus)

    def get_last_bonus(self):
        return self.bonuses[len(self.bonuses) - 1]

    def cancel_bonus(self):
        bonus = self.get_last_bonus()
        self.bonuses.remove(bonus)
        shared_own_amount = bonus.start_amount / 0.6
        self.shared_own_balance -= shared_own_amount
        self.own_balance += bonus.amount + shared_own_amount
        return bonus.amount

    def debug_stats(self):
        if logging.root.isEnabledFor(logging.DEBUG):
            self.log.debug(f'[ '
                           f'Total: {self.get_total_balance()} | '
                           f'Total own: {self.get_total_own_balance()} | '
                           f'Available for withdrawal: {self.get_own_balance()} | '
                           f'Bonus: {self.get_bonus_balance()} ]')


class Robot:
    def __init__(self, name, own_rate, bonuses_pieces, income_percent_per_cycle, min_working_amount,
                 working_amount_step,
                 max_working_amount, fuckup_probability_percent_per_cycle, bonus_work_percent_per_cycle):
        self.log = logging.getLogger(f'Robot {name}')
        self.name = name
        self.own_rate = own_rate
        self.bonuses_pieces = bonuses_pieces
        self.income_percent_per_cycle = income_percent_per_cycle
        self.min_working_amount = min_working_amount
        self.working_amount_step = working_amount_step
        self.max_working_amount = max_working_amount
        self.fuckup_probability_percent_per_cycle = fuckup_probability_percent_per_cycle
        self.bonus_work_percent_per_cycle = bonus_work_percent_per_cycle
        self.balance_limit = 12000
        self.account = Account(name)
        self.withdraw_failures = 0
        self.bonus_cancellations = 0
        self.bonus_cancellation_failures = 0
        self.fuckup_count = 0

    def fuck_it_all_up(self):
        loss = self.account.get_total_own_balance()
        bonus_loss = self.account.get_bonus_balance()
        self.fuckup_count += 1
        self.account.total_loss += loss
        self.account.total_bonus_loss += bonus_loss
        self.account.own_balance = 0
        self.account.shared_own_balance = 0
        self.account.bonuses = []
        self.log.info(f'FUCKED IT ALL UP! Losing {loss} own and {bonus_loss} bonus money')
        self.account.total_loss += loss
        self.account.debug_stats()
        self.debug_stats()
        return -loss

    def is_lucky(self):
        return random.random() > self.fuckup_probability_percent_per_cycle

    def work_cycle(self):
        working_amount = self.account.get_total_balance()
        if working_amount < self.min_working_amount:
            self.log.info(f'Account balance {working_amount} is less than '
                          f'minimum working amount {self.min_working_amount}')
            return 0
        if not self.is_lucky():
            return self.fuck_it_all_up()
        if working_amount > self.max_working_amount:
            working_amount = self.max_working_amount
        else:
            step = self.working_amount_step
            if step > working_amount:
                step = self.min_working_amount
            working_amount = working_amount - working_amount % step
        income = working_amount * self.income_percent_per_cycle
        self.account.earn(income)
        self.account.work_bonus(self.bonus_work_percent_per_cycle)
        self.debug_stats()
        return income

    def debug_stats(self):
        if logging.root.isEnabledFor(logging.DEBUG):
            self.log.debug(f'[ '
                           f'Total earnings: {self.account.total_earnings} | '
                           f'Total loss: {self.account.total_loss} | '
                           f'Total bonuses loss: {self.account.total_bonus_loss} | '
                           f'Total bonuses completed: {self.account.total_bonus_completed} | '
                           # f'Total withdrawn: {self.account.total_withdrawn} | '
                           f'Withdraw failures: {self.withdraw_failures} | '
                           f'Bonus cancellations: {self.bonus_cancellations} | '
                           f'Bonus cancellation failures: {self.bonus_cancellation_failures} | '
                           f'Fuckup count: {self.fuckup_count} ]')


class Strategy:
    def __init__(self, robots, start_amount, add_funds_per_period, robots_total_balance_limit):
        self.log = logging.getLogger('Strategy')
        self.withdraw_money_period = 7
        self.add_funds_period = 30
        self.rebalance_period = 30
        self.robots = robots
        self.start_amount = start_amount
        self.add_funds_per_period = add_funds_per_period
        self.robots_total_balance_limit = robots_total_balance_limit
        self.wallet = start_amount
        self.cycles = 0
        self.total_invested = start_amount
        self.rebalance()

    def get_total_profit(self):
        # logging.debug(self.get_total_withdrawn() + self.get_robots_total_own_balance() - self.get_total_deposited_amount())
        # logging.debug(self.get_total_own_balance() - self.get_max_invested_amount())
        # assert self.get_total_withdrawn() + self.get_robots_total_own_balance() - self.get_total_deposited_amount() \
        #        - (self.get_total_own_balance() - self.get_max_invested_amount()) < 0.001
        # return self.get_total_withdrawn() + self.get_robots_total_own_balance() - self.get_total_deposited_amount()
        return self.get_total_own_balance() - self.total_invested

    def get_total_earnings(self):
        return sum(robot.account.total_earnings for robot in self.robots)

    # def get_total_withdrawn(self):
    #     return sum(robot.account.total_withdrawn for robot in self.robots)

    # def get_total_deposited_amount(self):
    #     return sum(robot.account.total_deposit for robot in self.robots)

    def get_robots_total_balance(self):
        return sum(robot.account.get_total_balance() for robot in self.robots)

    def get_robots_total_own_balance(self):
        return sum(robot.account.get_total_own_balance() for robot in self.robots)

    def get_robots_own_balance(self):
        return sum(robot.account.get_own_balance() for robot in self.robots)

    def get_robots_shared_own_balance(self):
        return sum(robot.account.shared_own_balance for robot in self.robots)

    def get_robots_bonus_balance(self):
        return sum(robot.account.get_bonus_balance() for robot in self.robots)

    def get_total_fuckup_count(self):
        return sum(robot.fuckup_count for robot in self.robots)

    def get_total_loss(self):
        return sum(robot.account.total_loss for robot in self.robots)

    def get_total_bonus_loss(self):
        return sum(robot.account.total_bonus_loss for robot in self.robots)

    def get_total_own_balance(self):
        return self.get_robots_total_own_balance() + self.wallet

    def get_total_withdraw_failures(self):
        return sum(robot.withdraw_failures for robot in self.robots)

    def get_total_bonus_cancellations(self):
        return sum(robot.bonus_cancellations for robot in self.robots)

    def get_total_bonus_cancellations_failures(self):
        return sum(robot.bonus_cancellation_failures for robot in self.robots)

    def get_total_bonus_completed(self):
        return sum(robot.account.total_bonus_completed for robot in self.robots)

    def can_cancel_bonuses(self):
        return self.wallet + self.get_robots_own_balance() - self.get_robots_bonus_balance() > 0

    def rebalance(self):
        total_own_balance = self.get_total_own_balance()
        optimal_reserve = total_own_balance / 2
        optimal_robot_balance = (total_own_balance - optimal_reserve) / len(self.robots)
        max_robot_balance = max([robot.account.get_total_own_balance() for robot in self.robots])
        max_minimal_deposit = max([robot.min_working_amount for robot in self.robots])
        target_robot_balance = max(optimal_robot_balance, max_robot_balance, max_minimal_deposit)
        robot_balance_limit = self.robots_total_balance_limit / len(self.robots)
        if target_robot_balance > robot_balance_limit:
            target_robot_balance = robot_balance_limit
        for robot in self.robots:
            if target_robot_balance > robot.max_working_amount:
                target_robot_balance = robot.max_working_amount
        for robot in self.robots:
            if robot.account.get_total_balance() < robot.min_working_amount \
                    and self.wallet / robot.own_rate < robot.min_working_amount:
                self.log.info(f'Not enough money in wallet ({self.wallet}) to start {robot.name}: '
                              f'minimal deposit is {robot.min_working_amount}')
                continue
            step = robot.working_amount_step
            if target_robot_balance < robot.working_amount_step:
                step = robot.min_working_amount
            expected_own_rate = robot.own_rate
            actual_own_rate = robot.account.get_own_rate()
            # if actual_own_rate < expected_own_rate:
            #     expected_own_rate = 1
            target_robot_balance_considering_step = target_robot_balance - target_robot_balance % step
            balance_deficit = target_robot_balance_considering_step - robot.account.get_total_balance()
            own_rate_diff = actual_own_rate - expected_own_rate
            if own_rate_diff > 0.01:
                total_own_balance = robot.account.get_total_own_balance()
                own_balance_excess = total_own_balance * own_rate_diff
                if own_balance_excess >= robot.account.own_balance:
                    own_balance_excess = robot.account.own_balance
                    if own_balance_excess > 1:
                        robot.account.withdraw(own_balance_excess)
                        self.wallet += own_balance_excess
                        balance_deficit += own_balance_excess
            if own_rate_diff < -0.01:
                total_own_balance = robot.account.get_total_own_balance()
                own_balance_deficit = total_own_balance * own_rate_diff
                if own_balance_deficit > balance_deficit:
                    own_balance_deficit = balance_deficit
                    if own_balance_deficit > 1:
                        robot.account.deposit(own_balance_deficit, 1)
                        self.wallet -= own_balance_deficit
                    balance_deficit -= own_balance_deficit
            amount_to_add = balance_deficit * expected_own_rate
            if amount_to_add < 0.01:
                continue
            if amount_to_add > self.wallet:
                max_possible_balance = robot.account.get_total_balance() + self.wallet / expected_own_rate
                amount_to_add = (max_possible_balance - max_possible_balance % step -
                                 robot.account.get_total_balance()) * expected_own_rate
            self.wallet -= amount_to_add
            robot.account.deposit(amount_to_add, expected_own_rate, robot.bonuses_pieces)
            self.log.debug(f'Cycle {self.cycles} - rebalanced')

    def work_cycle(self):
        fucked_it_up = False
        for robot in self.robots:
            if robot.work_cycle() <= 0:
                fucked_it_up = True
        self.cycles += 1
        if self.should_add_funds():
            self.wallet += self.add_funds_per_period
            self.total_invested += self.add_funds_per_period
            self.log.debug(f'Cycle {self.cycles} - invested {self.add_funds_per_period}')
        if self.should_withdraw() or fucked_it_up:
            for robot in self.robots:
                robot_balance = robot.account.get_total_balance()
                if robot_balance == 0:
                    continue
                step = robot.working_amount_step
                if robot_balance < robot.working_amount_step:
                    step = robot.min_working_amount
                amount_to_withdraw = robot_balance % step
                if amount_to_withdraw < 0.01:
                    continue
                if robot.account.can_withdraw(amount_to_withdraw):
                    robot.account.withdraw(amount_to_withdraw)
                    self.wallet += amount_to_withdraw
                else:
                    remaining_own_balance = robot.account.own_balance
                    self.log.info(f'Can\'t withdraw {amount_to_withdraw} from {robot.name}: '
                                  f'{remaining_own_balance} own balance remaining')
                    robot.withdraw_failures += 1
                    if remaining_own_balance > 0.01:
                        robot.account.withdraw(remaining_own_balance)
                        self.wallet += remaining_own_balance
                        amount_to_withdraw -= remaining_own_balance
                    while amount_to_withdraw > 0.01:
                        if len(robot.account.bonuses) == 0:
                            self.log.warning(f'Can\'t cancel bonus: no bonuses')
                            robot.bonus_cancellation_failures += 1
                            break
                        last_bonus = robot.account.get_last_bonus()
                        if self.wallet >= last_bonus.amount:
                            self.log.info(f'Cancelling {last_bonus.amount} bonuses from {robot.name}')
                            bonus_amount = robot.account.cancel_bonus()
                            self.wallet -= bonus_amount
                            robot.bonus_cancellations += 1
                            assert self.wallet > 0
                            account_own_balance = robot.account.own_balance
                            if account_own_balance <= amount_to_withdraw:
                                robot.account.withdraw(account_own_balance)
                                self.wallet += account_own_balance
                                amount_to_withdraw -= account_own_balance
                            else:
                                robot.account.withdraw(amount_to_withdraw)
                                amount_to_withdraw = 0
                        else:
                            self.log.warning(f'Can\'t cancel bonus: {self.wallet} < {last_bonus.amount}')
                            robot.bonus_cancellation_failures += 1
                            break
        if self.should_rebalance() or fucked_it_up:
            self.rebalance()
        self.debug_stats()

    def should_withdraw(self):
        return self.cycles % self.withdraw_money_period == 0

    def should_add_funds(self):
        return self.cycles % self.add_funds_period == 0

    def should_rebalance(self):
        return self.cycles % self.rebalance_period == 0 or self.should_withdraw() or self.should_add_funds()

    def debug_stats(self):
        if logging.root.isEnabledFor(logging.DEBUG):
            self.log.debug(f'[ '
                           f'Cycles lived: {self.cycles} | '
                           f'Profit: {self.get_total_profit()} | '
                           f'Invested: {self.total_invested} | '
                           # f'Deposited: {self.get_total_deposited_amount()} | '
                           # f'Withdrawn: {self.get_total_withdrawn()} | '
                           # f'Withdrawn - Deposited: {self.get_total_withdrawn() - self.get_total_deposited_amount()} | '
                           f'Earnings: {self.get_total_earnings()} | '
                           f'Total own balance: {self.get_total_own_balance()} | '
                           f'Wallet balance: {self.wallet} | '
                           f'Robots total balance: {self.get_robots_total_balance()} | '
                           f'Robots total own balance: {self.get_robots_total_own_balance()} | '
                           f'Robots own balance (available for withdrawal): {self.get_robots_own_balance()} | '
                           f'Robots shared own balance: {self.get_robots_shared_own_balance()} | '
                           f'Robots bonus balance: {self.get_robots_bonus_balance()} | '
                           f'Fuckups survived: {self.get_total_fuckup_count()} | '
                           f'Total loss: {self.get_total_loss()} | '
                           f'Withdraw failures: {self.get_total_withdraw_failures()} | '
                           f'Bonus cancellations: {self.get_total_bonus_cancellations()} | '
                           f'Bonuses cancellation failures: {self.get_total_bonus_cancellations_failures()} | '
                           f'Bonuses lost: {self.get_total_bonus_loss()} | '
                           f'Bonuses completed: {self.get_total_bonus_completed()} | '
                           f']')


class RobotTestCase:
    def __init__(self, robot_balance_limit, cycles, total_runs, name, own_rate, bonuses_pieces,
                 income_percent_per_cycle, min_working_amount, working_amount_step, max_working_amount,
                 fuckup_probability_percent_per_cycle, bonus_work_percent_per_cycle, start_amount, add_funds_per_period,
                 robots_total_balance_limit, summary_log):
        self.robot_balance_limit = robot_balance_limit
        self.cycles = cycles
        self.total_runs = total_runs
        self.name = name
        self.own_rate = own_rate
        self.bonuses_pieces = bonuses_pieces
        self.income_percent_per_cycle = income_percent_per_cycle
        self.min_working_amount = min_working_amount
        self.working_amount_step = working_amount_step
        self.max_working_amount = max_working_amount
        self.fuckup_probability_percent_per_cycle = fuckup_probability_percent_per_cycle
        self.bonus_work_percent_per_cycle = bonus_work_percent_per_cycle
        self.start_amount = start_amount
        self.add_funds_per_period = add_funds_per_period
        self.robots_total_balance_limit = robots_total_balance_limit
        self.negative_outcomes = 0
        self.positive_outcomes = 0
        self.total_profit = 0
        self.total_balance = 0
        self.total_bonus_balance = 0
        self.best_outcome = 0
        self.worst_outcome = 0
        self.invested = 0
        # self.total_deposited = 0
        # self.total_withdrawn = 0
        # self.withdrawn_minus_deposited = 0
        self.withdraw_failures = 0
        self.bonus_cancellations = 0
        self.bonus_cancellation_failures = 0
        self.bonuses_lost = 0
        self.bonuses_completed = 0
        self.summary_log = summary_log
        self.errors = 0

    def run(self):
        log_name = f'{self.name}_own_rate-{self.own_rate}_bonuses_pieces-{self.bonuses_pieces}_cycles-{self.cycles}.log'
        if os.path.exists(log_name):
            return
        handler = logging.FileHandler(log_name)
        logging.root.addHandler(handler)
        logging.root.setLevel(logging.DEBUG)
        for i in range(self.total_runs):
            robot = Robot(self.name, self.own_rate, self.bonuses_pieces, self.income_percent_per_cycle,
                          self.min_working_amount, self.working_amount_step, self.max_working_amount,
                          self.fuckup_probability_percent_per_cycle, self.bonus_work_percent_per_cycle)
            strategy = Strategy([robot], self.start_amount, self.add_funds_per_period, self.robots_total_balance_limit)
            for j in range(self.cycles):
                strategy.work_cycle()
            profit = strategy.get_total_profit()
            if profit <= 0:
                self.negative_outcomes += 1
                if profit < self.worst_outcome:
                    self.worst_outcome = profit
            else:
                self.positive_outcomes += 1
                if self.best_outcome < profit:
                    self.best_outcome = profit
            self.total_profit += profit
            self.total_balance += strategy.get_robots_total_balance() + strategy.wallet
            self.total_bonus_balance += strategy.get_robots_bonus_balance()
            self.invested += strategy.total_invested
            # total_deposited += strategy.get_total_deposited_amount()
            # total_withdrawn += strategy.get_total_withdrawn()
            # withdrawn_minus_deposited += strategy.get_total_withdrawn() - strategy.get_total_deposited_amount()
            self.withdraw_failures += strategy.get_total_withdraw_failures()
            self.bonus_cancellations += strategy.get_total_bonus_cancellations()
            self.bonus_cancellation_failures += strategy.get_total_bonus_cancellations_failures()
            self.bonuses_lost += strategy.get_total_bonus_loss()
            self.bonuses_completed += strategy.get_total_bonus_completed()
            logging.root.setLevel(logging.ERROR)
        logging.root.setLevel(logging.INFO)
        logging.info(f'Total runs: {self.total_runs} by {self.cycles} cycles')
        logging.info(f'Positive outcomes: {self.positive_outcomes}')
        logging.info(f'Negative outcomes: {self.negative_outcomes}')
        logging.info(f'Average profit: {self.total_profit / self.total_runs}')
        logging.info(f'Average total balance: {self.total_balance / self.total_runs}')
        logging.info(f'Average total bonus balance: {self.total_bonus_balance / self.total_runs}')
        logging.info(f'Best outcome: {self.best_outcome}')
        logging.info(f'Worst outcome: {self.worst_outcome}')
        logging.info(f'Invested: {self.invested / self.total_runs}')
        # logging.info(f'Total deposited: {self.total_deposited / self.total_runs}')
        # logging.info(f'Total withdrawn: {self.total_withdrawn / self.total_runs}')
        # logging.info(f'Withdrawn - deposited: {self.withdrawn_minus_deposited / self.total_runs}')
        logging.info(f'Withdraw failures: {self.withdraw_failures / self.total_runs}')
        logging.info(f'Bonus cancellations: {self.bonus_cancellations / self.total_runs}')
        logging.info(f'Bonus cancellation failures: {self.bonus_cancellation_failures / self.total_runs}')
        logging.info(f'Bonuses lost: {self.bonuses_lost / self.total_runs}')
        logging.info(f'Bonuses completed: {self.bonuses_completed / self.total_runs}')
        logging.root.removeHandler(handler)
        self.log_summary()

    def log_summary(self):
        self.summary_log.info(f'{self.name},'
                              f'{self.own_rate},'
                              f'{self.bonuses_pieces},'
                              f'{self.total_runs},'
                              f'{self.cycles},'
                              f'{self.positive_outcomes},'
                              f'{self.negative_outcomes},'
                              f'{self.total_profit / self.total_runs},'
                              f'{self.total_balance / self.total_runs},'
                              f'{self.total_bonus_balance / self.total_runs},'
                              f'{self.best_outcome},'
                              f'{self.worst_outcome},'
                              f'{self.invested / self.total_runs},'
                              # f'{self.total_deposited / self.total_runs},'
                              # f'{self.total_withdrawn / self.total_runs},'
                              # f'{self.withdrawn_minus_deposited / self.total_runs},'
                              f'{self.withdraw_failures / self.total_runs},'
                              f'{self.bonus_cancellations / self.total_runs},'
                              f'{self.bonus_cancellation_failures / self.total_runs},'
                              f'{self.bonuses_lost / self.total_runs},'
                              f'{self.bonuses_completed / self.total_runs},'
                              f'{self.errors}')


def test_safe():
    summary_log = logging.getLogger('summary-safe')
    handler = logging.FileHandler(f'summary-SAFE.csv')
    summary_log.addHandler(handler)
    error_log = logging.getLogger('error')
    error_handler = logging.FileHandler(f'error-SAFE.log')
    error_log.addHandler(error_handler)

    if not os.path.exists(f'summary-SAFE.csv'):
        summary_log.warning(f'Name,'
                            f'Own rate,'
                            f'Bonus pieces,'
                            f'Total runs,'
                            f'Cycles,'
                            f'Positive outcomes,'
                            f'Negative outcomes,'
                            f'Average profit,'
                            f'Average balance,'
                            f'Average bonus balance,'
                            f'Best outcome,'
                            f'Worst outcome,'
                            f'Average invested,'
                            # f'Average deposited,'
                            # f'Average withdrawn,'
                            # f'Average withdrawn minus deposited,'
                            f'Average withdraw failures,'
                            f'Average bonus cancellations,'
                            f'Average bonus cancellation failures,'
                            f'Average bonuses lost,'
                            f'Average bonuses completed,'
                            f'Errors')
    test_cases = [RobotTestCase(12000, cycles, 100000,
                                'SAFE', own_rate, bonuses_pieces, 0.05 / 30, 1000, 2000, 12000, 0.01 / 30,
                                0.02 / 12 / 30,
                                1000, 1000, 12000, summary_log)
                  for cycles in [12 * 30, 24 * 30, 36 * 30]
                  for own_rate in [i / 100 for i in range(100, 62, -1)]
                  for bonuses_pieces in range(1, 20)]
    for test_case in test_cases:
        try:
            test_case.run()
        except Exception as e:
            test_case.errors += 1
            error_log.exception(f'Name: {test_case.name}, '
                                f'own rate: {test_case.own_rate}, '
                                f'bonus pieces: {test_case.bonuses_pieces},'
                                f'error: {e}')
            print(e)


def test_safe_mm100():
    summary_log = logging.getLogger('summary-safe_mm100')
    handler = logging.FileHandler(f'summary-SAFE_MM100.csv')
    summary_log.addHandler(handler)
    error_log = logging.getLogger('error')
    error_handler = logging.FileHandler(f'error-SAFE_MM100.log')
    error_log.addHandler(error_handler)

    if not os.path.exists(f'summary-SAFE_MM100.csv'):
        summary_log.warning(f'Name,'
                            f'Own rate,'
                            f'Bonus pieces,'
                            f'Total runs,'
                            f'Cycles,'
                            f'Positive outcomes,'
                            f'Negative outcomes,'
                            f'Average profit,'
                            f'Average balance,'
                            f'Average bonus balance,'
                            f'Best outcome,'
                            f'Worst outcome,'
                            f'Average invested,'
                            # f'Average deposited,'
                            # f'Average withdrawn,'
                            # f'Average withdrawn minus deposited,'
                            f'Average withdraw failures,'
                            f'Average bonus cancellations,'
                            f'Average bonus cancellation failures,'
                            f'Average bonuses lost,'
                            f'Average bonuses completed,'
                            f'Errors')
    test_cases = [RobotTestCase(12000, cycles, 100000,
                                'SAFE_MM100', own_rate, bonuses_pieces, 0.1 / 30, 1000, 1000, 12000, 0.05 / 30,
                                0.02 / 12 / 30,
                                1000, 1000, 12000, summary_log)
                  for cycles in [12 * 30, 24 * 30, 36 * 30]
                  for own_rate in [i / 100 for i in range(100, 62, -1)]
                  for bonuses_pieces in range(1, 20)]
    for test_case in test_cases:
        try:
            test_case.run()
        except Exception as e:
            test_case.errors += 1
            error_log.exception(f'Name: {test_case.name}, '
                                f'own rate: {test_case.own_rate}, '
                                f'bonus pieces: {test_case.bonuses_pieces},'
                                f'error: {e}')
            print(e)


def test_max():
    summary_log = logging.getLogger('summary-MAX')
    handler = logging.FileHandler(f'summary-MAX.csv')
    summary_log.addHandler(handler)
    error_log = logging.getLogger('error')
    error_handler = logging.FileHandler(f'error-MAX.log')
    error_log.addHandler(error_handler)

    if not os.path.exists(f'summary-max.csv'):
        summary_log.warning(f'Name,'
                            f'Own rate,'
                            f'Bonus pieces,'
                            f'Total runs,'
                            f'Cycles,'
                            f'Positive outcomes,'
                            f'Negative outcomes,'
                            f'Average profit,'
                            f'Average balance,'
                            f'Average bonus balance,'
                            f'Best outcome,'
                            f'Worst outcome,'
                            f'Average invested,'
                            # f'Average deposited,'
                            # f'Average withdrawn,'
                            # f'Average withdrawn minus deposited,'
                            f'Average withdraw failures,'
                            f'Average bonus cancellations,'
                            f'Average bonus cancellation failures,'
                            f'Average bonuses lost,'
                            f'Average bonuses completed,'
                            f'Errors')
    test_cases = [RobotTestCase(12000, cycles, 100000,
                                'MAX', own_rate, bonuses_pieces, 0.15 / 30, 500, 500, 12000, 0.1 / 30,
                                0.06 / 12 / 30,
                                1000, 1000, 12000, summary_log)
                  for cycles in [12 * 30, 24 * 30, 36 * 30]
                  for own_rate in [i / 100 for i in range(100, 62, -1)]
                  for bonuses_pieces in range(1, 20)]
    for test_case in test_cases:
        try:
            test_case.run()
        except Exception as e:
            test_case.errors += 1
            error_log.exception(f'Name: {test_case.name}, '
                                f'own rate: {test_case.own_rate}, '
                                f'bonus pieces: {test_case.bonuses_pieces},'
                                f'error: {e}')
            print(e)


def test_gxu():
    summary_log = logging.getLogger('summary-GXU')
    handler = logging.FileHandler(f'summary-GXU.csv')
    summary_log.addHandler(handler)
    error_log = logging.getLogger('error')
    error_handler = logging.FileHandler(f'error-GXU.log')
    error_log.addHandler(error_handler)

    if not os.path.exists(f'summary-gxu.csv'):
        summary_log.warning(f'Name,'
                            f'Own rate,'
                            f'Bonus pieces,'
                            f'Total runs,'
                            f'Cycles,'
                            f'Positive outcomes,'
                            f'Negative outcomes,'
                            f'Average profit,'
                            f'Average balance,'
                            f'Average bonus balance,'
                            f'Best outcome,'
                            f'Worst outcome,'
                            f'Average invested,'
                            # f'Average deposited,'
                            # f'Average withdrawn,'
                            # f'Average withdrawn minus deposited,'
                            f'Average withdraw failures,'
                            f'Average bonus cancellations,'
                            f'Average bonus cancellation failures,'
                            f'Average bonuses lost,'
                            f'Average bonuses completed,'
                            f'Errors')
    test_cases = [RobotTestCase(12000, cycles, 100000,
                                'GXU', own_rate, bonuses_pieces, 0.5 / 30, 1000, 1000, 12000, 0.4 / 30,
                                0.01 / 12 / 30,
                                1000, 1000, 12000, summary_log)
                  for cycles in [12 * 30, 24 * 30, 36 * 30]
                  for own_rate in [i / 100 for i in range(100, 62, -1)]
                  for bonuses_pieces in range(1, 20)]
    for test_case in test_cases:
        try:
            test_case.run()
        except Exception as e:
            test_case.errors += 1
            error_log.exception(f'Name: {test_case.name}, '
                                f'own rate: {test_case.own_rate}, '
                                f'bonus pieces: {test_case.bonuses_pieces},'
                                f'error: {e}')
            print(e)


def test():
    logging.root.setLevel(logging.DEBUG)

    robot_balance_limit = 12000

    cycles = 36 * 30
    total_runs = 100

    negative_outcomes = 0
    positive_outcomes = 0
    total_profit = 0
    total_balance = 0
    total_bonus_balance = 0
    best_outcome = 0
    worst_outcome = 0
    invested = 0
    total_deposited = 0
    total_withdrawn = 0
    withdrawn_minus_deposited = 0
    withdraw_failures = 0
    bonus_cancellations = 0
    bonus_cancellation_failures = 0
    bonuses_lost = 0
    bonuses_completed = 0

    for i in range(total_runs):
        # handler = logging.FileHandler(f'run{i}.log')
        # logging.root.addHandler(handler)
        robot_safe = Robot('SAFE', .77, 14, 0.05 / 30, 1000, 2000, robot_balance_limit, 0.01 / 30, 0.02 / 12 / 30)
        robot_x = Robot('X', .76, 4, 0.15 / 30, 300, 300, robot_balance_limit, 0.1 / 30, 0.06 / 12 / 30)
        robot_max = Robot('MAX', .9, 4, 0.15 / 30, 500, 500, robot_balance_limit, 0.1 / 30, 0.06 / 12 / 30)

        robot_gx = Robot('GX', 1, 1, 0.15 / 30, 1000, 1000, robot_balance_limit, 0.1 / 30, 0.01 / 12 / 30)
        # strategy = Strategy([robot_safe, robot_x, robot_max, robot_gx], 16000, 4000, robot_balance_limit * 4)
        strategy = Strategy([robot_safe], 1000, 1000, 12000)
        for j in range(cycles):
            strategy.work_cycle()
        # for robot in strategy.robots:
        #     robot.debug_stats()
        #     robot.account.debug_stats()
        profit = strategy.get_total_profit()
        if profit <= 0:
            negative_outcomes += 1
            if profit < worst_outcome:
                worst_outcome = profit
        else:
            positive_outcomes += 1
            if best_outcome < profit:
                best_outcome = profit
        total_profit += profit
        total_balance += strategy.get_robots_total_balance() + strategy.wallet
        total_bonus_balance += strategy.get_robots_bonus_balance()
        invested += strategy.total_invested
        # total_deposited += strategy.get_total_deposited_amount()
        # total_withdrawn += strategy.get_total_withdrawn()
        # withdrawn_minus_deposited += strategy.get_total_withdrawn() - strategy.get_total_deposited_amount()
        withdraw_failures += strategy.get_total_withdraw_failures()
        bonus_cancellations += strategy.get_total_bonus_cancellations()
        bonus_cancellation_failures += strategy.get_total_bonus_cancellations_failures()
        bonuses_lost += strategy.get_total_bonus_loss()
        bonuses_completed += strategy.get_total_bonus_completed()
        logging.root.setLevel(logging.WARNING)
        # logging.root.removeHandler(handler)

    # strategy.debug_stats()
    logging.root.setLevel(logging.INFO)
    logging.info(f'Total runs: {total_runs} by {cycles} cycles')
    logging.info(f'Positive outcomes: {positive_outcomes}')
    logging.info(f'Negative outcomes: {negative_outcomes}')
    logging.info(f'Average profit: {total_profit / total_runs}')
    logging.info(f'Average total balance: {total_balance / total_runs}')
    logging.info(f'Average total bonus balance: {total_bonus_balance / total_runs}')
    logging.info(f'Best outcome: {best_outcome}')
    logging.info(f'Worst outcome: {worst_outcome}')
    logging.info(f'Invested: {invested / total_runs}')
    # logging.info(f'Total deposited: {total_deposited / total_runs}')
    # logging.info(f'Total withdrawn: {total_withdrawn / total_runs}')
    # logging.info(f'Withdrawn - deposited: {withdrawn_minus_deposited / total_runs}')
    logging.info(f'Withdraw failures: {withdraw_failures / total_runs}')
    logging.info(f'Bonus cancellations: {bonus_cancellations / total_runs}')
    logging.info(f'Bonus cancellation failures: {bonus_cancellation_failures / total_runs}')
    logging.info(f'Bonuses lost: {bonuses_lost / total_runs}')
    logging.info(f'Bonuses completed: {bonuses_completed / total_runs}')


if __name__ == '__main__':
    # test_safe()
    # test_safe_mm100()
    # test_max()
    test_gxu()
    # random.seed(1)
    # test()
