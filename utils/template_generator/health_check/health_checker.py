from collections import defaultdict


class HealthChecker:

    values_dict = defaultdict(list)

    def check_in_dict(self, key, value):
        is_exist = self.values_dict.get(key, False)
        if is_exist:
            try:
                for item in is_exist:
                    if item == value:
                        return True
                self.values_dict[key].append(value)
                return False
            except Exception as e:
                raise Exception(f'Error while checking the health for key: {key} and value: {value}.\n\nContent of dictionary: {self.values_dict}\n\nError: {e}\n\nIsExist value: {is_exist}')
        else:
            self.values_dict[key].append(value)
            return False