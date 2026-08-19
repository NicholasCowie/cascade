

% k = [k1f k1b k2f k2b k3 k4f k4b k5f k5b k6]
k = [log(2)/120  0  log(2)/180 0 0.1 log(2)/120 0 log(2)/180 0 0.1]'; % 1/s

A0 = 20; % pmol/L 
E0 = 10000; % pmol/L
F0 = 10000; % pmol/L
x0 = [A0;E0;0;0;0;F0;0;0;0];

function f=cascade(t,x,k)
% x= [A E EA EAact B F FB FBact C]
A=x(1); E=x(2); EA=x(3); EAact=x(4); B=x(5); F=x(6); FB=x(7); FBact=x(8); C=x(9);
% k= [k1f k1b k2f k2b k3 k4f k4b k5f k5b k6]
k1f=k(1); k1b=k(2); k2f=k(3); k2b=k(4); k3= k(5); k4f= k(6); k4b=k(7); k5f=k(8); k5b=k(9); k6=k(10);

f =[-k1f*A*E+k1b*EA
    -k1f*A*E+k1b*EA
    k1f*A*E-k1b*EA-k2f*EA+k2b*EAact
    k2f*EA-k2b*EAact
    k3*EAact-k4f*B*F+k4b*FB
    -k4f*B*F+k4b*FB
    k4f*B*F-k4b*FB-k5f*FB+k5b*FBact
    k5f*FB-k5b*FBact
    k6*FBact];
end
clf
A600s=[];
A0 = [0:5:40]
for temp=A0
    x0 = [temp;E0;0;0;0;F0;0;0;0];    
    [t,x]=ode15s(@(t,x) cascade(t,x,k),[0:600],x0);
    A600s = [A600s;x(length(t),9)];
    figure('Name',strcat("Concentration of A: ",string(temp)," pmol/L"),'NumberTitle','off')
    subplot(2,2,1); plot(t,x(:,[1:4])); legend("A","E","EA","EAact");
    subplot(2,2,2); plot(t,x(:,[5])); legend("B");
    subplot(2,2,3); plot(t,x(:,[6:8])); legend("F","FB","FBact");
    subplot(2,2,4); plot(t,x(:,[9])); legend("C")
end
figure('Name','Signal at 600s','NumberTitle','off')
plot(A0,A600s)

