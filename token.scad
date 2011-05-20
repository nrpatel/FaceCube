file = "asdf.stl";
xin = 200;
yin = 200;

echo(file);

h = 2;
r = 15;
rim_h = 0.5;
rim_r = 2;

max_dim = max(xin, yin);
s = (r*1.8)/max_dim;

difference() {
    union() {
        translate([0,0,h/2]) scale([s,s,s]) import_stl(file);
        difference() {
            cylinder(h=h+rim_h,r=r);
            cylinder(h=h+rim_h,r=r-rim_r);
        }
        cylinder(h=h,r=r);
    }
    translate([0,0,-40]) cylinder(h=40,r=100);
	difference() {
		cylinder(h=100,r=100);
		cylinder(h=100,r=r);
	}
}
