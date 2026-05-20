
void print_string(int str[]){
    int size = str[0];
    int i = 1;
    while (i <= size) {
        out(str[i], 0);
        i = i + 1;
    }
}


int done = 0;

int buf[100];
int buf_i = 1;

__interrupt__(0)
void handle_input_data(){
    buf[buf_i] = in(0);
    buf_i = buf_i + 1;
    buf[0] = buf_i - 1;
}


__interrupt__(1)
void handle_input_end(){
    int flag = in(1);
    if (flag) {
        done = 1;
    }
}

int main() {
    print_string("What is your name?");
    while (!done) { 
        // wait for input
    }
    print_string("Hello, ");
    print_string(buf);
    print_string("!");
    return 0;
}