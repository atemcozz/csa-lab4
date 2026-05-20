
void sort(int arr[]) {
    int size = arr[0];
    int i = 1;
   while (i < size) {
        int min_i = i;
        int min_val = arr[i]; 
        int j = i + 1;

        while (j <= size) {
            int cur = arr[j]; 
            if (cur < min_val) {
                min_val = cur;
                min_i = j;
            }
            j = j + 1;
        }

        if (min_i != i) {
            arr[min_i] = arr[i];
            arr[i] = min_val;
        }
        i = i + 1;
    }
}


void parse_nums(int str[], int nums[]) {
    int str_size = str[0];
    int i = 1;
    int num_count = 0;
    int current_num = 0;
    int in_num = 0;
    int sign = 1;

    while (i <= str_size) {
        int char_val = str[i];
        if (char_val == ' ') {
            if (in_num) {
                num_count = num_count + 1;
                nums[num_count] = current_num * sign;
                current_num = 0;
                in_num = 0;
                sign = 1;
            }
        } else if (char_val == '-') {
            sign = -1;
            in_num = 1;
        } else {
            current_num = current_num * 10 + (char_val - '0');
            in_num = 1;
        }
        i = i + 1;
    }

    if (in_num) {
        num_count = num_count + 1;
        nums[num_count] = current_num * sign;
    }

    nums[0] = num_count;
}


int str[1001];
int str_i = 0;

int nums[101];
int nums_i = 0;

int input_done = 0;

__interrupt__(0)
void handle_input() {
    int val = in(0);
    
    str[str_i] = val;

    str_i = str_i + 1;

    if (str_i > str[0]) {
        input_done = 1;
    }

}

void print_abs(int n) {
    int d = n / 10;
    if (d > 0) {
        print_abs(d);
    }
    out((n - d * 10) + '0', 0);
}

void print_num(int n) {
    if (n < 0) {
        out('-', 0);
        n = -n;
    }
    print_abs(n);
}

int main() {

    while (!input_done) {
        // wait for input
    }


    parse_nums(str, nums);
    sort(nums);

    int i = 1;
    int size = nums[0];
    while (i <= size) {
        print_num(nums[i]);
        if (i < size) {
            out(' ', 0);
        }
        i = i + 1;
    }

    return 0;
}