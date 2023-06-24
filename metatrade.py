import logging
import random

LOG_FORMAT = '[%(levelname)s] %(name)s: %(message)s'
logging.basicConfig(format=LOG_FORMAT)


class Account:
    def __init__(self, name):
        self.log = logging.getLogger(f'Account {name}')
        self.name = name
        self.own_balance = 0
        self.shared_own_balance = 0
        self.bonus_balance = 0
        self.total_deposit = 0
        self.total_earnings = 0
        self.total_withdrawn = 0
        self.total_loss = 0
        self.total_bonus_loss = 0

    def get_total_balance(self):
        return self.own_balance + self.shared_own_balance + self.bonus_balance

    def get_own_balance(self):
        return self.own_balance

    def get_total_own_balance(self):
        return self.own_balance + self.shared_own_balance

    def get_own_rate(self):
        total_balance = self.get_total_balance()
        if total_balance == 0:
            return 1
        return self.get_total_own_balance() / self.get_total_balance()

    def deposit(self, amount, own_rate):
        shared_own_amount = amount * (1 / own_rate - 1) / 0.6
        own_amount = amount - shared_own_amount
        bonus_amount = shared_own_amount * 0.6
        self.own_balance += own_amount
        self.shared_own_balance += shared_own_amount
        self.bonus_balance += bonus_amount
        self.log.debug(f'Deposit {amount}')
        self.total_deposit += amount
        self.debug_stats()

    def withdraw(self, amount):
        if not self.can_withdraw(amount):
            raise ValueError(f'Can\'t withdraw {amount}: own balance is {self.own_balance}')
        self.own_balance -= amount
        self.log.debug(f'Withdraw {amount}')
        self.total_withdrawn += amount
        self.debug_stats()

    def can_withdraw(self, amount):
        return self.own_balance >= amount

    def earn(self, amount):
        total_balance = self.get_total_balance()
        own_share = self.get_total_own_balance() / total_balance
        bonus_share = self.bonus_balance / total_balance
        self.own_balance += amount * own_share
        self.bonus_balance += amount * bonus_share
        self.log.debug(f'Earned {amount}')
        self.total_earnings += amount
        self.debug_stats()

    def cancel_bonus(self):
        self.own_balance = self.get_total_balance()
        self.shared_own_balance = 0
        self.bonus_balance = 0

    def debug_stats(self):
        self.log.debug(f'[ '
                       f'Total: {self.get_total_balance()} | '
                       f'Total own: {self.get_total_own_balance()} | '
                       f'Available for withdrawal: {self.get_own_balance()} | '
                       f'Bonus: {self.bonus_balance} ]')


class Robot:
    def __init__(self, name, own_rate, income_percent_per_cycle, min_working_amount, working_amount_step,
                 fuckup_probability_percent_per_cycle):
        self.log = logging.getLogger(f'Robot {name}')
        self.name = name
        self.own_rate = own_rate
        self.income_percent_per_cycle = income_percent_per_cycle
        self.min_working_amount = min_working_amount
        self.working_amount_step = working_amount_step
        self.fuckup_probability_percent_per_cycle = fuckup_probability_percent_per_cycle
        self.account = Account(name)
        self.fuckup_count = 0
        pass

    def fuck_it_all_up(self):
        loss = self.account.get_total_own_balance()
        bonus_loss = self.account.bonus_balance
        self.fuckup_count += 1
        self.account.total_loss += loss
        self.account.total_bonus_loss += bonus_loss
        self.account.own_balance = 0
        self.account.shared_own_balance = 0
        self.account.bonus_balance = 0
        self.log.info(f'FUCKED IT ALL UP! Losing {loss} own and {bonus_loss} bonus money')
        self.account.total_loss += loss
        self.account.debug_stats()
        self.debug_stats()
        return -loss

    def is_lucky(self):
        return random.random() > self.fuckup_probability_percent_per_cycle

    def work_cycle(self):
        account_balance = self.account.get_total_balance()
        if account_balance < self.min_working_amount:
            self.log.info(f'Account balance {self.account.get_total_balance()} is less than '
                          f'minimum working amount {self.min_working_amount}')
            return 0
        if not self.is_lucky():
            return self.fuck_it_all_up()
        step = self.working_amount_step
        if step > account_balance:
            step = self.min_working_amount
        working_amount = account_balance - account_balance % step
        income = working_amount * self.income_percent_per_cycle
        self.account.earn(income)
        self.debug_stats()
        return income

    def debug_stats(self):
        self.log.debug(f'[ '
                       f'Total income: {self.account.total_earnings} | '
                       f'Total loss: {self.account.total_loss} | '
                       f'Total withdrawn: {self.account.total_withdrawn} | '
                       f'Fuckup count: {self.fuckup_count} ]')


class Strategy:
    def __init__(self, robots, start_amount, add_funds_per_cycle, robots_total_balance_limit):
        self.log = logging.getLogger('Strategy')
        self.robots = robots
        self.start_amount = start_amount
        self.add_funds_per_cycle = add_funds_per_cycle
        self.robots_total_balance_limit = robots_total_balance_limit
        self.wallet = start_amount
        self.cycles = 0
        self.rebalance()

    def get_total_profit(self):
        # logging.debug(self.get_total_withdrawn() + self.get_robots_total_own_balance() - self.get_total_deposited_amount())
        # logging.debug(self.get_total_own_balance() - self.get_max_invested_amount())
        # assert self.get_total_withdrawn() + self.get_robots_total_own_balance() - self.get_total_deposited_amount() \
        #        - (self.get_total_own_balance() - self.get_max_invested_amount()) < 0.001
        # return self.get_total_withdrawn() + self.get_robots_total_own_balance() - self.get_total_deposited_amount()
        return self.get_total_own_balance() - self.get_max_invested_amount()

    def get_total_earnings(self):
        return sum([robot.account.total_earnings for robot in self.robots])

    def get_total_withdrawn(self):
        return sum([robot.account.total_withdrawn for robot in self.robots])

    def get_total_deposited_amount(self):
        return sum([robot.account.total_deposit for robot in self.robots])

    def get_max_invested_amount(self):
        return self.start_amount + self.cycles * self.add_funds_per_cycle

    def get_robots_total_balance(self):
        return sum([robot.account.get_total_balance() for robot in self.robots])

    def get_robots_total_own_balance(self):
        return sum([robot.account.get_total_own_balance() for robot in self.robots])

    def get_robots_own_balance(self):
        return sum([robot.account.get_own_balance() for robot in self.robots])

    def get_robots_shared_own_balance(self):
        return sum([robot.account.shared_own_balance for robot in self.robots])

    def get_robots_bonus_balance(self):
        return sum([robot.account.bonus_balance for robot in self.robots])

    def get_total_fuckup_count(self):
        return sum([robot.fuckup_count for robot in self.robots])

    def get_total_loss(self):
        return sum([robot.account.total_loss for robot in self.robots])

    def get_total_bonus_loss(self):
        return sum([robot.account.total_bonus_loss for robot in self.robots])

    def get_total_own_balance(self):
        return self.get_robots_total_own_balance() + self.wallet

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
            if robot.account.get_total_balance() < robot.min_working_amount \
                    and self.wallet / robot.own_rate < robot.min_working_amount:
                self.log.warning(f'Not enough money in wallet ({self.wallet}) to start {robot.name}: '
                                 f'minimal deposit is {robot.min_working_amount}')
                continue
            step = robot.working_amount_step
            if target_robot_balance < robot.working_amount_step:
                step = robot.min_working_amount
            own_rate = robot.own_rate
            # if robot.account.get_own_rate() < own_rate:
            #     own_rate = 1
            target_robot_balance_considering_step = target_robot_balance - target_robot_balance % step
            amount_to_add = (target_robot_balance_considering_step - robot.account.get_total_balance()) * own_rate
            if amount_to_add > self.wallet:
                max_possible_balance = robot.account.get_total_balance() + self.wallet / own_rate
                amount_to_add = (max_possible_balance - max_possible_balance % step -
                                 robot.account.get_total_balance()) * own_rate
            if amount_to_add <= 0:
                continue
            self.wallet -= amount_to_add
            robot.account.deposit(amount_to_add, own_rate)

    def work_cycle(self):
        for robot in self.robots:
            result = robot.work_cycle()
            if result > 0:
                if robot.account.can_withdraw(result):
                    robot.account.withdraw(result)
                    self.wallet += result
                else:
                    remaining_own_balance = robot.account.own_balance
                    self.log.info(f'Can\'t withdraw {result} from {robot.name}: '
                                  f'{remaining_own_balance} own balance remaining')
                    if remaining_own_balance > 0:
                        robot.account.withdraw(remaining_own_balance)
                        self.wallet += remaining_own_balance
                    if self.wallet >= robot.account.bonus_balance:
                        self.log.info(f'Cancelling {robot.account.bonus_balance} bonuses from {robot.name}')
                        self.wallet -= robot.account.bonus_balance
                        robot.account.cancel_bonus()
                        self.wallet += robot.account.get_total_balance()
                        robot.account.withdraw(robot.account.get_total_balance())
                    else:
                        self.log.warning(f'Can\'t cancel bonuses: {self.wallet} < {robot.account.bonus_balance}')
        self.cycles += 1
        self.log.debug(f'Cycle {self.cycles} - investing {self.add_funds_per_cycle}')
        self.wallet += self.add_funds_per_cycle
        self.rebalance()
        strategy.debug_stats()

    def debug_stats(self):
        self.log.debug(f'[ '
                       f'Cycles lived: {self.cycles} | '
                       f'Profit: {self.get_total_profit()} | '
                       f'Deposited: {self.get_total_deposited_amount()} | '
                       f'Invested: {self.get_max_invested_amount()} | '
                       f'Withdrawn: {self.get_total_withdrawn()} | '
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
                       f'Bonuses lost: {self.get_total_bonus_loss()} | '
                       f'Can cancel bonuses: {self.can_cancel_bonuses()} '
                       f']')


if __name__ == '__main__':
    logging.root.setLevel(logging.DEBUG)
    own_rate = 1

    cycles = 12
    negative_outcomes = 0
    positive_outcomes = 0
    total_runs = 10000
    total_profit = 0
    best_outcome = 0
    worst_outcome = 0
    for i in range(total_runs):
        robot_safe = Robot('SAFE', own_rate, 0.05, 1000, 2000, 0.01)
        robot_x = Robot('X', own_rate, 0.15, 300, 300, 0.1)
        robot_max = Robot('MAX', own_rate, 0.15, 500, 500, 0.1)
        robot_gx = Robot('GX', own_rate, 0.15, 1000, 1000, 0.1)
        strategy = Strategy([robot_safe, robot_x, robot_max, robot_gx], 16000, 4000, 12000 * 4)
        for i in range(cycles):
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
        logging.root.setLevel(logging.ERROR)
    logging.root.setLevel(logging.DEBUG)
    # strategy.debug_stats()
    logging.info(f'Own rate: {own_rate}')
    logging.info(f'Total runs: {total_runs} by {cycles} cycles')
    logging.info(f'Positive outcomes: {positive_outcomes}')
    logging.info(f'Negative outcomes: {negative_outcomes}')
    logging.info(f'Average profit: {total_profit / total_runs}')
    logging.info(f'Best outcome: {best_outcome}')
    logging.info(f'Worst outcome: {worst_outcome}')
