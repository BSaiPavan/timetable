package collections;
public class Sudoko{
public int box[][] = {
    {0,0,0, 2,0,7, 0,9,0},
    {5,0,0, 0,0,0, 0,0,0},
    {0,0,0, 0,1,0, 8,0,5},

    {0,0,6, 9,3,0, 0,0,0},
    {0,0,5, 8,0,0, 0,0,3},
    {0,0,4, 0,7,0, 1,2,0},

    {0,4,1, 0,0,0, 0,0,0},
    {0,0,9, 0,4,0, 0,8,0},
    {3,6,0, 0,0,0, 0,0,2}
};
   public void print(){
               for (int[] row : box) {
              for (int c : row) {
                System.out.print(c + " ");
            }
              System.out.println();
        } 
   }
   public boolean rowsafe(int n,Node node){
          return rsafe(n,node,box,0);}
   boolean rsafe(int n,Node node ,int box[][],int i){
          int x=node.x;
          int y=node.y;
          if(i>=box[0].length)
              return true;
          if(box[x][i] == n)
                return false;
          return rsafe(n,node,box,i+1);
   }
   public boolean columnsafe(int n,Node node){
          return csafe(n,node,box,0);}
   boolean csafe(int n,Node node,int box[][],int i){
         int x=node.x;
          int y=node.y;
          if(i>=box.length)
              return true;
          if(box[i][y] == n)
                return false;
          return csafe(n,node,box,i+1);
   }
   Node findblock(Node node){
      int x=node.x;
      int y=node.y;
      return new Node(x/3,y/3);
   }
   public boolean blocksafe(int n,Node node){
          Node block = findblock(node);
          return bsafe(n,block);
          }
boolean bsafe(int n, Node block) {
    int r = block.x * 3;
    int c = block.y * 3;
    for(int i = 0; i < 3; i=i+1) {
        for(int j = 0; j < 3; j=j+1) {
            if(box[r + i][c + j] == n)
                return false;
        }
    }
    return true;
}

    public boolean issafe(int n,Node node){
          if(blocksafe(n,node) && columnsafe(n,node) && rowsafe(n,node) )
                  return true;
              return false;
    }
    public  Node findnextspace(){
        for(int r=0;r<9;r=r+1){
            for(int c=0;c<9;c=c+1){
                if(box[r][c]==0)
                    return new Node(r,c);
            }
        }
          return new Node(-1,-1);
    }
     public boolean solve(){
          Node n=this.findnextspace();
          if(n.x==-1)
              return true;
          for(int i=1;i<=9;i=i+1){
              if(issafe(i,n)){
                 box[n.x][n.y]=i;
                 if(solve())
                        return true;
                 }
              box[n.x][n.y]=0;
    
              }
          return false;
     }   
   
   
}
