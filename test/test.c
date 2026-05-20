
// Global variable declaration (identifier, type, literal)
int globalVar = 10;

int global_string[] = "Global string literal";

int int_global_array[5];
// Function declaration (keyword, identifier, parentheses, braces)
int add(int a, int b) {
    // return statement (keyword, operator, identifiers)
    return a + b;  // arithmetic operator +
}


__interrupt__(5)
int array_first(int arr[]) {
    int local_arr_inside_fn[3];
    return arr[0];  // array access
}
void fn(){
    int local_arr_inside_empty_fn[3];
}


void print_char(int c) {
    out(c, 0);  // function call (identifier + parentheses)
}

// Main function
int main() {

    out('H', 0);
    out('e', 0);
    out('l', 0);
    out('l', 0);
    out('o', 0);
    
    int min = -2147483648;
    int t = 2 + 2 * 2;
    // integer literal, assignment operator
    int x = 5;
    // char literal
    int c = 'A';

    // string literal
    int str[] = "Hello, world!";
    int local_int_array[3];
    local_int_array[0] = 1;  // array access and assignment

    str[2] = 'X';  // array access and assignment
    // arithmetic operators
    int sum = x;
    int diff = x - 3;
    int mul = x * 2;
    int div = x / 2;
    int complex = (mul + 2) * (div - 1) / 3;
    // relational operators
    if (x > 0 && x < 10) {
        // logical operators &&, comparison >
        x = x + 1;
        int array_inside_if[2];
    }


    // bitwise operators
    int bit = x & 1;
    bit = bit | 2;
    bit = bit << 1;
    bit = bit >> 1;


    // while loop
    while (x > 0) {
        int local_arr_inside_while[3];
        x = x - 1;
        
    }
    // function call (identifier + parentheses)
    int result = add(x, 20);


    return 0;
}