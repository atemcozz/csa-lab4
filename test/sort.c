
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

int nums[101]; 
int nums_i = 0;
int done = 0;

__interrupt__(0)
void handle_input() {
    int val = in(0);
    
    nums[nums_i] = val;

    nums_i = nums_i + 1;

    if (nums_i > nums[0]) {
        done = 1;
    }

}



int main() {

    while (!done) {
        // wait for input
    }

    sort(nums);

    int i = 1;
    int size = nums[0];
    while (i <= size) {
        out(nums[i], 0);
        i = i + 1;
    }

    return 0;
}